"""Prepare and display a static image on a Hongtai panel."""

from __future__ import annotations

import argparse
from .device import HongtaiPanel
from .rendering import encode_jpeg, fit_panel_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Display an image on a Hongtai panel")
    parser.add_argument("image", help="PNG, JPEG, or other Pillow-supported image")
    parser.add_argument("--device", default="/dev/ttyACM0", help="serial device path")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=320)
    parser.add_argument("--quality", type=int, default=85)
    parser.add_argument(
        "--hold",
        type=float,
        default=0,
        help="seconds to keep displaying; 0 continues until Ctrl+C",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="send close command afterward (verified firmware may leave the panel blank)",
    )
    return parser


def prepare_jpeg(path: str, width: int, height: int, quality: int) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Image support requires Pillow. Install with: pip install -e '.[images]'"
        ) from exc

    with Image.open(path) as source:
        image = fit_panel_image(source, width, height)
        return encode_jpeg(image, quality=quality)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.hold < 0:
        raise SystemExit("--hold cannot be negative")
    jpeg = prepare_jpeg(args.image, args.width, args.height, args.quality)

    with HongtaiPanel(args.device) as panel:
        panel.send_jpeg(jpeg)
        try:
            panel.hold_display(None if args.hold == 0 else args.hold)
        except KeyboardInterrupt:
            print("\nDisplay hold stopped.")
        if args.release:
            panel.release_display()
    print(f"Displayed {args.image} ({len(jpeg)} JPEG bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
