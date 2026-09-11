from __future__ import annotations

import http.client
import threading
import unittest

from formatador_academico.web_app.server import create_server


class TestLocalWebServer(unittest.TestCase):
    def setUp(self):
        self.server = create_server("127.0.0.1", 0, token="test-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def _request(self, headers=None, path="/api/health"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
        connection.request("GET", path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, body

    def test_health_requires_session_token(self):
        status, body = self._request()
        self.assertEqual(status, 401)
        self.assertIn(b"session token required", body)

    def test_health_accepts_expected_token_and_origin(self):
        status, body = self._request(
            {
                "Host": f"{self.host}:{self.port}",
                "X-Formatador-Session": "test-token",
                "Origin": f"http://{self.host}:{self.port}",
                "Sec-Fetch-Site": "same-origin",
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body, b'{"service":"formatador-academico","status":"ok"}')

    def test_health_rejects_cross_site_origin(self):
        status, _ = self._request(
            {
                "Host": f"{self.host}:{self.port}",
                "X-Formatador-Session": "test-token",
                "Origin": "https://example.com",
            }
        )
        self.assertEqual(status, 403)

    def test_health_rejects_cross_site_fetch(self):
        status, _ = self._request(
            {
                "Host": f"{self.host}:{self.port}",
                "X-Formatador-Session": "test-token",
                "Sec-Fetch-Site": "cross-site",
            }
        )
        self.assertEqual(status, 403)

    def test_unexpected_host_is_rejected(self):
        status, _ = self._request(
            {"Host": "localhost:8000", "X-Formatador-Session": "test-token"}
        )
        self.assertEqual(status, 400)

    def test_unknown_route_is_not_exposed(self):
        status, _ = self._request(
            {"Host": f"{self.host}:{self.port}", "X-Formatador-Session": "test-token"},
            path="/",
        )
        self.assertEqual(status, 404)

    def test_server_is_local_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
