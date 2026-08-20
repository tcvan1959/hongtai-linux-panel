"""Local-only visual layout editor and validated layout storage."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .layout import Layout


class EditorStore:
    """Read and atomically replace one validated layout document."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def load_dict(self) -> dict[str, Any]:
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {self.path}: {exc}") from exc
        if not isinstance(values, dict):
            raise ValueError("layout must be a JSON object")
        Layout.from_dict(values, asset_root=self.path.parent)
        return values

    def save_dict(self, values: Any) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("layout must be a JSON object")
        Layout.from_dict(values, asset_root=self.path.parent)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(values, indent=2, ensure_ascii=False) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return values


@dataclass(frozen=True, slots=True)
class EditorServer:
    httpd: ThreadingHTTPServer
    url: str
    controller: Any | None = None

    def serve_forever(self) -> None:
        self.httpd.serve_forever()

    def close(self) -> None:
        try:
            if self.controller is not None:
                self.controller.close()
        finally:
            self.httpd.server_close()


def create_editor_server(
    layout_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    controller: Any | None = None,
    control_mode: bool = False,
) -> EditorServer:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("the editor may only listen on localhost")
    store = EditorStore(layout_path)
    store.load_dict()
    token = secrets.token_urlsafe(32)
    assets = Path(__file__).resolve().parent / "editor_assets"

    class Handler(BaseHTTPRequestHandler):
        server_version = "HongtaiLayoutEditor/0.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(
            self,
            status: HTTPStatus,
            body: bytes,
            content_type: str,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: HTTPStatus, values: Any) -> None:
            body = (json.dumps(values, ensure_ascii=False) + "\n").encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802
            request = urlsplit(self.path)
            path = request.path
            if path == "/api/panel/status" and controller is not None:
                self._json(
                    HTTPStatus.OK,
                    {"panel": controller.snapshot(), "token": token},
                )
                return
            if path == "/api/panel/preview" and controller is not None:
                layout = parse_qs(request.query).get("layout", ["orientation"])[0]
                try:
                    body = controller.preview(layout)
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                    return
                self._send(HTTPStatus.OK, body, "image/jpeg")
                return
            if path == "/api/layout":
                try:
                    self._json(HTTPStatus.OK, {"layout": store.load_dict(), "token": token})
                except (OSError, ValueError) as exc:
                    self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            filenames = {"/editor.css": ("editor.css", "text/css; charset=utf-8")}
            if control_mode:
                filenames.update(
                    {
                        "/": ("control.html", "text/html; charset=utf-8"),
                        "/control.js": (
                            "control.js",
                            "text/javascript; charset=utf-8",
                        ),
                    }
                )
            else:
                filenames.update(
                    {
                        "/": ("index.html", "text/html; charset=utf-8"),
                        "/editor.js": (
                            "editor.js",
                            "text/javascript; charset=utf-8",
                        ),
                    }
                )
            asset = filenames.get(path)
            if asset is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            try:
                body = (assets / asset[0]).read_bytes()
            except OSError as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
                return
            self._send(HTTPStatus.OK, body, asset[1])

        def do_PUT(self) -> None:  # noqa: N802
            if urlsplit(self.path).path != "/api/layout":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            if not secrets.compare_digest(self.headers.get("X-Editor-Token", ""), token):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid editor token"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 1_000_000:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid request size"})
                return
            try:
                values = json.loads(self.rfile.read(length))
                saved = store.save_dict(values)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"layout": saved, "saved": True})

        def do_POST(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if controller is None or not path.startswith("/api/"):
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            if not secrets.compare_digest(self.headers.get("X-Control-Token", ""), token):
                self._json(HTTPStatus.FORBIDDEN, {"error": "invalid control token"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 0 or length > 64 * 1024:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid request size"})
                return
            try:
                values = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(values, dict):
                    raise ValueError("request must be a JSON object")
                if path == "/api/panel/detect":
                    panel = controller.detect()
                elif path == "/api/panel/start":
                    panel = controller.start(
                        values.get("layout", "orientation"),
                        values.get("brightness"),
                    )
                elif path == "/api/panel/stop":
                    panel = controller.stop()
                elif path == "/api/panel/brightness":
                    panel = controller.set_brightness(values.get("brightness"))
                elif path == "/api/panel/restore-default":
                    if values.get("confirmed") is not True:
                        raise ValueError("panel restart confirmation is required")
                    panel = controller.restore_default_display()
                elif path == "/api/app/exit":
                    panel = controller.stop()
                    self._json(HTTPStatus.OK, {"panel": panel, "exiting": True})
                    threading.Thread(
                        target=self.server.shutdown,
                        name="hongtai-control-shutdown",
                        daemon=True,
                    ).start()
                    return
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
            except (OSError, RuntimeError, TimeoutError, TypeError, ValueError) as exc:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": str(exc), "panel": controller.snapshot()},
                )
                return
            self._json(HTTPStatus.OK, {"panel": panel})

    httpd = ThreadingHTTPServer((host, port), Handler)
    address, selected_port = httpd.server_address[:2]
    display_host = "127.0.0.1" if address in {"0.0.0.0", "::"} else address
    return EditorServer(
        httpd=httpd,
        url=f"http://{display_host}:{selected_port}/",
        controller=controller,
    )
