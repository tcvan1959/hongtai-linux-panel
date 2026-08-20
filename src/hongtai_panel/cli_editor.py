"""Command-line launcher for the local visual layout editor."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from .config import default_config_path, load_config_if_present
from .editor import create_editor_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Edit a Hongtai panel layout visually")
    parser.add_argument("--layout", type=Path, help="layout JSON file")
    parser.add_argument("--config", type=Path, help="saved application configuration")
    parser.add_argument("--host", default="127.0.0.1", help="localhost address")
    parser.add_argument("--port", default=8765, type=int, help="local TCP port")
    parser.add_argument("--no-open", action="store_true", help="do not open a browser")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config_if_present(args.config or default_config_path())
        selected_layout = args.layout or (
            Path(config.layout_path) if config.layout_path is not None else None
        )
        if selected_layout is None:
            raise ValueError(
                "no saved layout is configured; specify one with --layout PATH"
            )
        server = create_editor_server(selected_layout, host=args.host, port=args.port)
    except (OSError, ValueError) as exc:
        print(f"Cannot start editor: {exc}", file=sys.stderr)
        return 2
    print(f"Hongtai layout editor: {server.url}")
    print(f"Editing: {selected_layout.resolve()}")
    if not args.no_open:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
