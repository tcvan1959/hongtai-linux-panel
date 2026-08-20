"""Launch the local-only Panel Control App v1."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .control_app import PanelController
from .editor import create_editor_server
from .layout import default_layout_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control the verified Hongtai panel")
    parser.add_argument("--device", help="serial path; omit for safe auto-detection")
    parser.add_argument(
        "--layout",
        type=Path,
        default=default_layout_path(),
        help="starter dashboard layout JSON",
    )
    parser.add_argument("--host", default="127.0.0.1", help="localhost address")
    parser.add_argument("--port", default=8765, type=int, help="local TCP port")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = PanelController(device_path=args.device, layout_path=args.layout)
    try:
        server = create_editor_server(
            args.layout,
            host=args.host,
            port=args.port,
            controller=controller,
            control_mode=True,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Cannot start Panel Control: {exc}", file=sys.stderr)
        return 2

    print(f"Hongtai Panel Control: {server.url}")
    print("Foreground-only session; use Exit app or Ctrl+C to close it.")
    if not args.no_open:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Panel Control…")
    try:
        server.close()
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f"Panel Control cleanup failed: {exc}", file=sys.stderr)
        return 1
    print("Panel Control stopped; no panel stream remains.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
