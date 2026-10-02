"""Local snapshot review server; no filesystem routes or Atlas transport."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
import json
from urllib.parse import urlsplit

from .review import review_snapshot_json

MAX_BODY_BYTES = 2 * 1024 * 1024
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}


class ReviewHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, format, *args):
        # Never log uploaded data or user filenames.
        return

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, result: dict):
        self._send(status, json.dumps(result, ensure_ascii=True, allow_nan=False).encode("utf-8"), "application/json")

    def _error(self, status: int, message: str):
        # Closing with an unread small POST body can reset TCP before the client
        # receives the rejection on Windows. Discard only a bounded declared body.
        if self.command == "POST" and not getattr(self, "_body_read", False):
            lengths = self.headers.get_all("Content-Length", [])
            try:
                length = int(lengths[0]) if len(lengths) == 1 else -1
                if 0 <= length <= MAX_BODY_BYTES and not self.headers.get("Transfer-Encoding"):
                    self.connection.settimeout(1)
                    self.rfile.read(length)
            except (ValueError, OSError):
                pass
            self._body_read = True
        self._json(status, {"scope": "snapshot_integrity", "submit_authorized": False,
                            "ok": False, "error": message, "status": "request_error"})

    def _local_request(self) -> bool:
        port = self.server.server_port
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in (f"127.0.0.1:{port}", f"localhost:{port}"):
            self._error(403, "Host must match the local review server")
            return False
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or (origins and origins[0] != "http://" + hosts[0]):
            self._error(403, "Origin must match the local review server")
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._error(403, "Cross-site requests are not supported")
            return False
        if not self.path.startswith("/") or self.path.startswith("//"):
            self._error(400, "Expected a local route")
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        route = urlsplit(self.path).path
        if route not in ASSETS:
            self._error(404, "Unknown route")
            return
        name, content_type = ASSETS[route]
        self._send(200, files("atlas_annotation").joinpath("ui", name).read_bytes(), content_type)

    def do_POST(self):
        if not self._local_request():
            return
        if self.path != "/api/review":
            self._error(404, "Unknown route")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self._error(415, "Use application/json with raw snapshot strings")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
            self._error(411, "One Content-Length is required; chunked bodies are not supported")
            return
        try:
            length = int(lengths[0])
            if length < 0:
                raise ValueError
        except ValueError:
            self._error(400, "Invalid Content-Length")
            return
        if length > MAX_BODY_BYTES:
            self._error(413, "Request exceeds 2 MiB")
            return
        try:
            body = self.rfile.read(length)
            self._body_read = True
            if len(body) != length:
                raise ValueError("Incomplete request body")
            request = json.loads(body.decode("utf-8"))
            allowed = {"live_json", "source_json", "plan_json", "tolerance_sec"}
            if not isinstance(request, dict) or set(request) - allowed:
                raise ValueError("Expected raw live_json/source_json and optional plan_json/tolerance_sec")
            if not isinstance(request.get("live_json"), str) or not isinstance(request.get("source_json"), str):
                raise ValueError("live_json and source_json must be raw JSON strings")
            if request.get("plan_json") is not None and not isinstance(request["plan_json"], str):
                raise ValueError("plan_json must be raw JSON text or null")
            result = review_snapshot_json(**request)
        except (ValueError, TypeError, OverflowError, RecursionError, TimeoutError) as exc:
            self._error(400, str(exc))
            return
        self._json(200, result)


def create_review_server(*, port: int = 8081) -> HTTPServer:
    """Create a server bound exclusively to IPv4 loopback (port=0 is for tests)."""
    return HTTPServer(("127.0.0.1", port), ReviewHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8081, help="Local port; 0 chooses an available port")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    with create_review_server(port=args.port) as server:
        print(f"Atlas snapshot review: http://127.0.0.1:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
