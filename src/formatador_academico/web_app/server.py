"""Authenticated local HTTP server for the web interface."""

from __future__ import annotations

import argparse
import base64
import json
import re
import secrets
import socket
from collections import deque
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files as resource_files
from threading import BoundedSemaphore, Timer
from typing import Any

from ..processing_session import DEFAULT_MAX_APPLIED_OPERATIONS
from ..product_delivery import (
    ProductDeliveryContractError,
    ProductDeliveryIntegrityError,
    DeliveryRole,
    build_product_delivery,
)
from ..product_input_boundary import (
    ProductInputBoundaryContractError,
    ProductInputBoundaryIntegrityError,
    ProductInputBoundaryUnsupportedError,
    build_product_from_inputs,
)

DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_CONNECTIONS = 32
DEFAULT_LOG_ENTRIES = 100
_SESSION_HEADER = "X-Formatador-Session"
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})
_PROCESS_PATH = "/api/process"
_MAX_FILENAME_CODEPOINTS = 255
_MAX_MULTIPART_BOUNDARY_BYTES = 200
_PUBLIC_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "connect-src 'self'; frame-ancestors 'none'"
)


def generate_session_token() -> str:
    """Return a fresh unpredictable token for one server process."""

    return secrets.token_urlsafe(32)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


class MultipartInputError(ValueError):
    """Malformed or incomplete multipart request."""


def _parse_multipart(content_type: str, body: bytes) -> dict[str, tuple[str, bytes]]:
    if not content_type.lower().startswith("multipart/form-data"):
        raise MultipartInputError("content type must be multipart/form-data")
    boundary_match = re.search(r"(?:^|;)\s*boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type, re.I)
    if boundary_match is None:
        raise MultipartInputError("multipart boundary is missing")
    boundary = boundary_match.group(1) or boundary_match.group(2)
    try:
        if len(boundary.encode("latin-1")) > _MAX_MULTIPART_BOUNDARY_BYTES:
            raise MultipartInputError("multipart boundary is too long")
        header = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("latin-1")
        )
    except UnicodeEncodeError as exc:
        raise MultipartInputError("multipart content type is invalid") from exc
    try:
        message = BytesParser(policy=policy.default).parsebytes(header + body)
    except (UnicodeError, ValueError) as exc:
        raise MultipartInputError("multipart body is invalid") from exc
    if not message.is_multipart() or message.defects:
        raise MultipartInputError("multipart body is invalid")

    fields: dict[str, tuple[str, bytes]] = {}
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            raise MultipartInputError("multipart part must be form-data")
        name = part.get_param("name", header="content-disposition")
        if not isinstance(name, str) or name not in {
            "document",
            "profile",
            "max_applied_operations",
        }:
            raise MultipartInputError("multipart field is not supported")
        if name in fields:
            raise MultipartInputError("multipart field is duplicated")
        filename = part.get_filename() or ""
        if len(filename) > _MAX_FILENAME_CODEPOINTS:
            raise MultipartInputError("multipart filename is too long")
        if any(ord(char) < 32 or ord(char) == 127 for char in filename):
            raise MultipartInputError("multipart filename is invalid")
        if name == "document":
            if not filename or "/" in filename or "\\" in filename:
                raise MultipartInputError("document filename is invalid")
            if (
                part.get_content_type()
                != "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ):
                raise MultipartInputError("document media type is invalid")
        elif name == "profile" and part.get_content_type() != "application/json":
            raise MultipartInputError("profile media type is invalid")
        content = part.get_payload(decode=True)
        if not isinstance(content, bytes) or not content:
            raise MultipartInputError("multipart field is empty")
        fields[name] = (filename, content)
    if set(fields) not in (
        {"document", "profile"},
        {"document", "profile", "max_applied_operations"},
    ):
        raise MultipartInputError("document and profile fields are required")
    return fields


class _Handler(BaseHTTPRequestHandler):
    server: "LocalWebServer"
    timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
    server_version = "FormatadorAcademico"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        # Never retain request lines, paths, headers or document metadata.
        return

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        # Keep only bounded operational counters for diagnostics.
        self.server.request_log.append((self.command, str(code)))

    def log_error(self, format: str, *args: Any) -> None:
        return

    def _reject(self, status: HTTPStatus, message: str) -> None:
        payload = _json_bytes({"error": message})
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _host_allowed(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in self.server.expected_hosts:
            self._reject(HTTPStatus.BAD_REQUEST, "host not allowed")
            return False
        return True

    def _request_target(self) -> str:
        parts = self.raw_requestline.split(b" ", 2)
        if len(parts) != 3:
            return ""
        try:
            return parts[1].decode("ascii")
        except UnicodeDecodeError:
            return ""

    def _authorized(self) -> bool:
        if not self._host_allowed():
            return False
        tokens = self.headers.get_all(_SESSION_HEADER, [])
        if len(tokens) != 1 or not secrets.compare_digest(tokens[0], self.server.token):
            self._reject(HTTPStatus.UNAUTHORIZED, "session token required")
            return False
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1:
            self._reject(HTTPStatus.BAD_REQUEST, "origin is duplicated")
            return False
        origin = origins[0] if origins else None
        if origin is not None and origin not in self.server.expected_origins:
            self._reject(HTTPStatus.FORBIDDEN, "origin not allowed")
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site not in _ALLOWED_FETCH_SITES:
            self._reject(HTTPStatus.FORBIDDEN, "cross-site request not allowed")
            return False
        return True

    def do_GET(self) -> None:
        if not self._host_allowed():
            return
        request_target = self._request_target()
        public = self.server.public_routes.get(request_target)
        if public is not None:
            self._send_public(*public)
            return
        if not self._authorized():
            return
        if request_target != "/api/health":
            self._reject(HTTPStatus.NOT_FOUND, "route not found")
            return
        payload = _json_bytes({"service": "formatador-academico", "status": "ok"})
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_public(self, content: bytes, media_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", _PUBLIC_CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        if self._request_target() != _PROCESS_PATH:
            self._reject(HTTPStatus.NOT_FOUND, "route not found")
            return
        try:
            fields = self._read_multipart_body()
            filename, document = fields["document"]
            _, profile = fields["profile"]
            if not filename.lower().endswith(".docx"):
                raise MultipartInputError("document filename must end with .docx")
            if not filename.rsplit(".", 1)[0]:
                raise MultipartInputError("document filename must have a base name")
            max_operations = self._read_max_applied_operations(fields)
            bundle = build_product_from_inputs(
                document, profile, max_applied_operations=max_operations
            )
            delivery = build_product_delivery(
                bundle, base_name=filename.rsplit(".", 1)[0]
            )
        except MultipartInputError as exc:
            self._reject(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except (ProductInputBoundaryContractError, ProductInputBoundaryUnsupportedError, ProductDeliveryContractError):
            self._reject(HTTPStatus.UNPROCESSABLE_ENTITY, "document or profile was rejected")
            return
        except (ProductInputBoundaryIntegrityError, ProductDeliveryIntegrityError):
            self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "processing integrity failure")
            return
        except Exception as exc:
            self.server.request_log.append((self.command, type(exc).__name__))
            self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "internal error")
            return
        try:
            self._send_delivery(delivery)
        except Exception as exc:
            self.server.request_log.append((self.command, type(exc).__name__))
            self._reject(HTTPStatus.INTERNAL_SERVER_ERROR, "internal error")

    def _read_max_applied_operations(self, fields: dict[str, tuple[str, bytes]]) -> int:
        if "max_applied_operations" not in fields:
            return DEFAULT_MAX_APPLIED_OPERATIONS
        _, raw = fields["max_applied_operations"]
        try:
            if re.fullmatch(rb"[0-9]+", raw) is None:
                raise MultipartInputError("max_applied_operations is invalid")
            value = int(raw, 10)
        except (UnicodeDecodeError, ValueError) as exc:
            raise MultipartInputError("max_applied_operations is invalid") from exc
        if value <= 0:
            raise MultipartInputError("max_applied_operations is invalid")
        if value > DEFAULT_MAX_APPLIED_OPERATIONS:
            raise MultipartInputError("max_applied_operations cannot exceed the default limit")
        return value

    def _read_multipart_body(self) -> dict[str, tuple[str, bytes]]:
        if self.headers.get_all("Transfer-Encoding", []):
            raise MultipartInputError("transfer encoding is not supported")
        content_lengths = self.headers.get_all("Content-Length", [])
        if len(content_lengths) > 1:
            raise MultipartInputError("content length is duplicated")
        content_length = content_lengths[0] if content_lengths else None
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError as exc:
                raise MultipartInputError("content length is invalid") from exc
            if length < 0 or length > self.server.max_body_bytes:
                raise MultipartInputError("request body exceeds the configured limit")
            body = self.rfile.read(length)
            if len(body) != length:
                raise MultipartInputError("request body is incomplete")
        else:
            body = self.rfile.read(self.server.max_body_bytes + 1)
            if len(body) > self.server.max_body_bytes:
                raise MultipartInputError("request body exceeds the configured limit")
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1:
            raise MultipartInputError("content type is missing or duplicated")
        return _parse_multipart(content_types[0], body)

    def _send_delivery(self, delivery) -> None:
        files = [
            {
                "role": item.role.value,
                "filename": item.filename,
                "media_type": item.media_type,
                "sha256": item.content_sha256,
                "size_bytes": item.size_bytes,
                "content_base64": base64.b64encode(item.content_bytes).decode("ascii"),
            }
            for item in delivery.files
        ]
        reports = [item for item in delivery.files if item.role is DeliveryRole.TECHNICAL_REPORT]
        if len(reports) != 1:
            raise ValueError("delivery must contain exactly one technical report")
        report = json.loads(reports[0].content_bytes.decode("utf-8"))
        payload = _json_bytes(
            {
                "status": "ok",
                "session_status": report["summary"]["session_status"],
                "summary": report["summary"],
                "files": files,
            }
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _method_not_allowed(self) -> None:
        if self._authorized():
            self._reject(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")

    do_OPTIONS = _method_not_allowed
    def do_HEAD(self) -> None:
        if not self._authorized():
            return
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    do_PUT = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_PATCH = _method_not_allowed


class LocalWebServer(ThreadingHTTPServer):
    """Threaded local server carrying immutable process-level security state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address,
        token: str,
        max_body_bytes: int,
        max_connections: int,
    ):
        super().__init__(server_address, _Handler)
        self.token = token
        self.max_body_bytes = max_body_bytes
        bound_host, bound_port = self.server_address
        self.expected_hosts = frozenset(
            {
                f"127.0.0.1:{bound_port}",
                f"localhost:{bound_port}",
                f"[::1]:{bound_port}",
            }
        )
        self.expected_origins = frozenset(f"http://{host}" for host in self.expected_hosts)
        package = resource_files("formatador_academico.web_app").joinpath("static")
        self.public_routes = {
            "/": (package.joinpath("index.html").read_bytes(), "text/html; charset=utf-8"),
            "/static/app.js": (
                package.joinpath("app.js").read_bytes(),
                "text/javascript; charset=utf-8",
            ),
            "/static/style.css": (
                package.joinpath("style.css").read_bytes(),
                "text/css; charset=utf-8",
            ),
        }
        self.request_log = deque(maxlen=DEFAULT_LOG_ENTRIES)
        self._connection_slots = BoundedSemaphore(max_connections)

    def process_request(self, request, client_address) -> None:
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        deadline = Timer(DEFAULT_REQUEST_TIMEOUT_SECONDS, self._expire_request, (request,))
        deadline.daemon = True
        deadline.start()
        try:
            super().process_request_thread(request, client_address)
        finally:
            deadline.cancel()
            self._connection_slots.release()

    @staticmethod
    def _expire_request(request) -> None:
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            request.close()
        except OSError:
            pass

    def handle_error(self, request, client_address) -> None:
        # Do not print tracebacks or client metadata for request failures.
        self.request_log.append(("ERROR", "internal"))


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    token: str | None = None,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    max_connections: int = DEFAULT_MAX_CONNECTIONS,
) -> LocalWebServer:
    """Create a local server without starting its serving loop."""

    if type(host) is not str or host != DEFAULT_HOST:
        raise ValueError("host must be 127.0.0.1")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be an integer between 0 and 65535")
    if token is not None and (type(token) is not str or not token):
        raise ValueError("token must be a non-empty str")
    if type(max_body_bytes) is not int or max_body_bytes <= 0:
        raise ValueError("max_body_bytes must be a positive int")
    if type(max_connections) is not int or max_connections <= 0:
        raise ValueError("max_connections must be a positive int")
    return LocalWebServer(
        (host, port), token or generate_session_token(), max_body_bytes, max_connections
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Formatador Acadêmico local web server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = create_server(port=args.port)
    print(f"Formatador Acadêmico: http://localhost:{args.port}/")
    print(f"Token de sessão: {server.token}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
