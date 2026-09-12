"""Small authenticated HTTP server for the local web interface.

This first slice exposes only a health endpoint. Document processing is added
in a later step after the transport and session boundary are tested.
"""

from __future__ import annotations

import argparse
import json
import secrets
from collections import deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import Any

DEFAULT_MAX_BODY_BYTES = 64 * 1024 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_MAX_CONNECTIONS = 32
DEFAULT_LOG_ENTRIES = 100
_SESSION_HEADER = "X-Formatador-Session"
_ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})


def generate_session_token() -> str:
    """Return a fresh unpredictable token for one server process."""

    return secrets.token_urlsafe(32)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


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

    def _authorized(self) -> bool:
        if self.headers.get("Host") not in self.server.expected_hosts:
            self._reject(HTTPStatus.BAD_REQUEST, "host not allowed")
            return False
        tokens = self.headers.get_all(_SESSION_HEADER, [])
        if len(tokens) != 1 or not secrets.compare_digest(tokens[0], self.server.token):
            self._reject(HTTPStatus.UNAUTHORIZED, "session token required")
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in self.server.expected_origins:
            self._reject(HTTPStatus.FORBIDDEN, "origin not allowed")
            return False
        fetch_site = self.headers.get("Sec-Fetch-Site")
        if fetch_site is not None and fetch_site not in _ALLOWED_FETCH_SITES:
            self._reject(HTTPStatus.FORBIDDEN, "cross-site request not allowed")
            return False
        return True

    def do_GET(self) -> None:
        if not self._authorized():
            return
        if self.path != "/api/health":
            self._reject(HTTPStatus.NOT_FOUND, "route not found")
            return
        payload = _json_bytes({"service": "formatador-academico", "status": "ok"})
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        self._reject(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")

    def _method_not_allowed(self) -> None:
        if self._authorized():
            self._reject(HTTPStatus.METHOD_NOT_ALLOWED, "method not allowed")

    do_OPTIONS = _method_not_allowed
    do_HEAD = _method_not_allowed
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
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()


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
