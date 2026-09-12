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

    def _request(self, headers=None, path="/api/health", method="GET"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        connection.close()
        return response.status, body

    def _request_with_headers(self, headers=None, path="/api/health", method="GET"):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        response_headers = dict(response.getheaders())
        connection.close()
        return response.status, response_headers, body

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

    def test_health_accepts_localhost_host(self):
        status, body = self._request(
            {
                "Host": f"localhost:{self.port}",
                "X-Formatador-Session": "test-token",
                "Origin": f"http://localhost:{self.port}",
            }
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"status":"ok"', body)

    def test_health_accepts_token_without_optional_browser_headers(self):
        status, body = self._request(
            {
                "Host": f"localhost:{self.port}",
                "X-Formatador-Session": "test-token",
            }
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"status":"ok"', body)

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

    def test_public_static_surface_is_exact_and_requires_host_only(self):
        expected = {
            "/",
            "/static/app.js",
            "/static/style.css",
        }
        self.assertEqual(set(self.server.public_routes), expected)
        for path in expected:
            with self.subTest(path=path):
                status, headers, body = self._request_with_headers(
                    {"Host": f"localhost:{self.port}"}, path=path
                )
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["Referrer-Policy"], "no-referrer")
                self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
                self.assertNotIn(b"test-token", body)

    def test_public_static_paths_are_not_a_file_server(self):
        for path in (
            "/static/../web_app/server.py",
            "/static/%2e%2e/x",
            "/static/app.js?v=1",
            "//static/app.js",
            "/static/",
            "/static/other.js",
        ):
            with self.subTest(path=path):
                status, _ = self._request({"Host": f"localhost:{self.port}"}, path=path)
                self.assertIn(status, (401, 404))

    def test_public_surface_rejects_unexpected_host(self):
        for path in ("/", "/static/app.js", "/static/style.css"):
            with self.subTest(path=path):
                status, _ = self._request({"Host": "evil.example:8000"}, path=path)
                self.assertEqual(status, 400)

    def test_public_surface_accepts_only_get(self):
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            with self.subTest(method=method):
                status, _ = self._request(
                    {"Host": f"localhost:{self.port}"}, path="/", method=method
                )
                self.assertIn(status, (401, 405))

    def test_unexpected_host_is_rejected(self):
        status, _ = self._request(
            {"Host": "evil.example:8000", "X-Formatador-Session": "test-token"}
        )
        self.assertEqual(status, 400)

    def test_unknown_route_is_authenticated_before_route_lookup(self):
        status, body = self._request(
            {"Host": f"localhost:{self.port}"},
            path="/not-a-route",
        )
        self.assertEqual(status, 401)
        self.assertIn(b"session token required", body)

    def test_options_is_denied_without_cors_headers(self):
        status, response_headers, body = self._request_with_headers(
            {
                "Host": f"localhost:{self.port}",
                "X-Formatador-Session": "test-token",
            },
            method="OPTIONS",
        )
        self.assertEqual(status, 405)
        self.assertIn(b"method not allowed", body)
        self.assertFalse(any(name.lower().startswith("access-control-") for name in response_headers))

    def test_methods_return_json_405(self):
        for method in ("HEAD", "PUT", "DELETE", "PATCH"):
            with self.subTest(method=method):
                status, body = self._request(
                    {
                        "Host": f"localhost:{self.port}",
                        "X-Formatador-Session": "test-token",
                    },
                    method=method,
                )
                self.assertEqual(status, 405)
                if method != "HEAD":
                    self.assertIn(b"method not allowed", body)

    def test_response_does_not_expose_python_version(self):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
        connection.request(
            "GET",
            "/api/health",
            headers={
                "Host": f"localhost:{self.port}",
                "X-Formatador-Session": "test-token",
            },
        )
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertNotIn("Python/", response.getheader("Server", ""))
        response.read()
        connection.close()

    def test_log_is_bounded_and_does_not_keep_paths(self):
        for _ in range(150):
            self._request(
                {
                    "Host": f"localhost:{self.port}",
                    "X-Formatador-Session": "test-token",
                }
            )
        self.assertLessEqual(len(self.server.request_log), 100)
        self.assertTrue(all("/api/health" not in str(entry) for entry in self.server.request_log))

    def test_duplicate_session_headers_are_rejected(self):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=2)
        connection.putrequest("GET", "/api/health", skip_host=True)
        connection.putheader("Host", f"localhost:{self.port}")
        connection.putheader("X-Formatador-Session", "test-token")
        connection.putheader("X-Formatador-Session", "other-token")
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 401)
        response.read()
        connection.close()

    def test_root_serves_the_public_application_page(self):
        status, body = self._request(
            {"Host": f"{self.host}:{self.port}", "X-Formatador-Session": "test-token"},
            path="/",
        )
        self.assertEqual(status, 200)
        self.assertIn("Formatador Acadêmico".encode("utf-8"), body)

    def test_public_page_contains_profile_values_accepted_by_the_core(self):
        status, _, body = self._request_with_headers(
            {"Host": f"localhost:{self.port}"}, path="/"
        )
        self.assertEqual(status, 200)
        self.assertIn(b'value="justify">justificado', body)
        self.assertNotIn(b'value="both">justificado', body)
        self.assertIn(b'value="10000"', body)
        self.assertIn(b'value="true">exigido', body)
        self.assertNotIn(b"Number(control.value)", self.server.public_routes["/static/app.js"][0])

    def test_page_explains_quiescent_and_uses_session_storage(self):
        script = self.server.public_routes["/static/app.js"][0]
        self.assertIn(b"Isso n\xc3\xa3o significa conformidade integral", script)
        self.assertIn(b"sessionStorage", script)
        self.assertNotIn(b"localStorage", script)

    def test_server_is_local_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_security_limits_are_configured(self):
        self.assertEqual(self.server.RequestHandlerClass.timeout, 30)
        self.assertEqual(self.server.request_log.maxlen, 100)
        self.assertEqual(
            self.server.expected_hosts,
            frozenset({
                f"127.0.0.1:{self.port}",
                f"localhost:{self.port}",
                f"[::1]:{self.port}",
            }),
        )


if __name__ == "__main__":
    unittest.main()
