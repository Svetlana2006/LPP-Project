"""Local JSON API used by the interactive allocation demonstration."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from food_allocation.demo import run_demo  # noqa: E402


class DemoApiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/api/health":
            self._send_json(404, {"error": "Not found."})
            return
        self._send_json(200, {"status": "ok"})

    def do_POST(self) -> None:
        if self.path != "/api/solve":
            self._send_json(404, {"error": "Not found."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length header."})
            return
        if content_length <= 0 or content_length > 1_000_000:
            self._send_json(400, {"error": "Request body must be between 1 byte and 1 MB."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            response = run_demo(payload)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        except RuntimeError as error:
            self._send_json(500, {"error": f"The optimizer could not solve this input: {error}"})
            return
        self._send_json(200, response)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[demo-api] {format % args}")


if __name__ == "__main__":
    port = int(os.environ.get("DEMO_API_PORT", "5174"))
    server = ThreadingHTTPServer(("127.0.0.1", port), DemoApiHandler)
    print(f"Food-allocation demo API listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
