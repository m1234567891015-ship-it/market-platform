"""Local HTTP fixtures for verifier checks that must not require external data.

The fixture server replays the committed API baseline files and manifest metadata
over loopback. It intentionally does not start app.py or make network requests;
live endpoint checks remain in verify_against_baseline.py's live mode.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def materialize_schema(value):
    """Turn schema markers into JSON values whose extracted schema is identical."""
    if isinstance(value, dict):
        return {key: materialize_schema(item) for key, item in value.items()}
    if isinstance(value, list):
        return [materialize_schema(value[0])] if value else []
    if value == "str":
        return "fixture"
    if value == "int":
        return 0
    if value == "float":
        return 0.0
    if value == "bool":
        return False
    return value


class OfflineFixtureServer:
    def __init__(self, manifest_path: Path, baseline_dir: Path):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._responses: dict[str, tuple[int, str, bytes]] = {}
        for endpoint in manifest["endpoints"]:
            fixture_path = baseline_dir / endpoint["baseline_file"]
            stored = json.loads(fixture_path.read_text(encoding="utf-8"))
            body = json.dumps(
                materialize_schema(stored) if endpoint["structure_only"] else stored,
                ensure_ascii=False,
            ).encode("utf-8")
            content_type = endpoint.get("content_type") or "application/json"
            self._responses[endpoint["request_path"]] = (
                int(endpoint["status_code"]),
                content_type,
                body,
            )

        responses = self._responses

        class FixtureHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                response = responses.get(self.path)
                if response is None:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "fixture not found"}).encode("utf-8"))
                    return
                status, content_type, body = response
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def __enter__(self) -> "OfflineFixtureServer":
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
