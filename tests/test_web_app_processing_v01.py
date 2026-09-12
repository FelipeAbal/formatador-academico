from __future__ import annotations

import base64
import io
import hashlib
import http.client
import json
import threading
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from formatador_academico.web_app.server import create_server

from test_analysis_formatting_v01b_m1 import build_docx, document, styles_part
from test_classification_v01_e2e import NORMAL


def _package() -> bytes:
    body = "".join(
        (
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:rPr><w:b/></w:rPr><w:t>web</w:t></w:r></w:p>',
            '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
            '<w:r><w:rPr><w:b/></w:rPr><w:t>second</w:t></w:r></w:p>',
        )
    )
    return build_docx(document(body), styles_part(NORMAL))


def _profile() -> bytes:
    return json.dumps(
        {
            "schema_version": "0.1",
            "profile": {"id": "web", "version": "1"},
            "rules": {"body": {"bold": {"mode": "exact", "value": False}}},
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _multipart(
    document_bytes: bytes,
    profile_bytes: bytes,
    *,
    operation_limit: int | None = None,
) -> bytes:
    boundary = b"web-test-boundary"
    prefix = b"--" + boundary
    parts = [
        (
            b'Content-Disposition: form-data; name="document"; filename="artigo.docx"\r\n'
            b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n"
            + document_bytes
        ),
        (
            b'Content-Disposition: form-data; name="profile"\r\n'
            b"Content-Type: application/json\r\n\r\n"
            + profile_bytes
        ),
    ]
    if operation_limit is not None:
        parts.append(
            b'Content-Disposition: form-data; name="max_applied_operations"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            + str(operation_limit).encode("ascii")
        )
    return b"\r\n".join(prefix + b"\r\n" + part for part in parts) + b"\r\n" + prefix + b"--\r\n"


class TestWebProcessing(unittest.TestCase):
    def setUp(self):
        self.server = create_server("127.0.0.1", 0, token="test-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def _post(self, body: bytes, content_type: str = "multipart/form-data; boundary=web-test-boundary"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        connection.request(
            "POST",
            "/api/process",
            body=body,
            headers={
                "Host": f"localhost:{self.port}",
                "X-Formatador-Session": "test-token",
                "Content-Type": content_type,
                "Content-Length": str(len(body)),
            },
        )
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response.status, payload

    def test_process_returns_all_delivery_files_in_one_response(self):
        status, payload = self._post(_multipart(_package(), _profile()))
        self.assertEqual(status, 200)
        result = json.loads(payload)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["files"]), 5)
        for item in result["files"]:
            decoded = base64.b64decode(item["content_base64"], validate=True)
            self.assertEqual(item["size_bytes"], len(decoded))
            self.assertEqual(item["sha256"], hashlib.sha256(decoded).hexdigest())

    def test_profile_bytes_are_passed_to_frozen_parser(self):
        profile = b'{"schema_version":"0.1","schema_version":"0.1","profile":{}}'
        status, payload = self._post(_multipart(_package(), profile))
        self.assertEqual(status, 422)
        self.assertIn(b"document or profile was rejected", payload)

    def test_body_limit_is_rejected_before_processing(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.server = create_server("127.0.0.1", 0, token="test-token", max_body_bytes=32)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address
        status, payload = self._post(_multipart(_package(), _profile()))
        self.assertEqual(status, 400)
        self.assertIn(b"exceeds", payload)

    def test_operation_limit_is_exposed_in_response_envelope(self):
        status, payload = self._post(_multipart(_package(), _profile(), operation_limit=1))
        self.assertEqual(status, 200)
        result = json.loads(payload)
        self.assertEqual(result["session_status"], "operation_limit_reached")
        self.assertEqual(result["summary"]["session_status"], "operation_limit_reached")

    def test_non_decimal_operation_limit_is_rejected(self):
        body = _multipart(_package(), _profile())
        body = body.replace(b"\r\n--web-test-boundary--", b"\r\n--web-test-boundary\r\n"
            b'Content-Disposition: form-data; name="max_applied_operations"\r\n'
            b"Content-Type: text/plain\r\n\r\n1_0\r\n--web-test-boundary--")
        status, payload = self._post(body)
        self.assertEqual(status, 400)
        self.assertIn(b"max_applied_operations is invalid", payload)

    def test_unexpected_pipeline_error_is_generic_and_does_not_traceback(self):
        stderr = io.StringIO()
        with patch(
            "formatador_academico.web_app.server.build_product_from_inputs",
            side_effect=RuntimeError("SECRET internal detail"),
        ), redirect_stderr(stderr):
            status, payload = self._post(_multipart(_package(), _profile()))
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(payload), {"error": "internal error"})
        self.assertNotIn("SECRET", stderr.getvalue())

    def test_boundary_integrity_error_is_not_reported_as_user_input_error(self):
        from formatador_academico.product_input_boundary import (
            ProductInputBoundaryIntegrityError,
            ProductInputStage,
        )

        error = ProductInputBoundaryIntegrityError("internal", "broken lineage", ProductInputStage.PRODUCT_OUTPUT)
        with patch(
            "formatador_academico.web_app.server.build_product_from_inputs",
            side_effect=error,
        ):
            status, payload = self._post(_multipart(_package(), _profile()))
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(payload), {"error": "processing integrity failure"})


if __name__ == "__main__":
    unittest.main()
