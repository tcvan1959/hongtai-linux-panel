"""Command-line device-information query."""

from __future__ import annotations

import argparse
import json

from .device import HongtaiPanel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query a Hongtai USB panel")
    parser.add_argument("--device", default="/dev/ttyACM0", help="serial device path")
    parser.add_argument("--timeout", type=float, default=3.0, help="response timeout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with HongtaiPanel(args.device) as panel:
        info = panel.query_device_info(args.timeout)
    print(json.dumps(info.raw, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
