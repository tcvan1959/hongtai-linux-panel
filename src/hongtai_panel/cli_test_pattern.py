"""Render and send the project's repeatable physical-panel test pattern."""

from __future__ import annotations

import argparse
from .device import HongtaiPanel
from .rendering import encode_jpeg, render_test_pattern


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display the Hongtai test pattern")
    parser.add_argument("--device", default="/dev/ttyACM0", help="serial device path")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument(
        "--hold",
        type=float,
        default=0,
        help="seconds to keep displaying; 0 continues until Ctrl+C",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="send close command afterward (verified firmware may become blank)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.hold < 0:
        raise SystemExit("--hold cannot be negative")
    jpeg = encode_jpeg(render_test_pattern(args.width, args.height))

    with HongtaiPanel(args.device) as panel:
        panel.send_jpeg(jpeg)
        try:
            panel.hold_display(None if args.hold == 0 else args.hold)
        except KeyboardInterrupt:
            print("\nDisplay hold stopped.")
        if args.release:
            panel.release_display()

    print(
        f"Displayed {args.width}x{args.height} test pattern "
        f"({len(jpeg)} JPEG bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
