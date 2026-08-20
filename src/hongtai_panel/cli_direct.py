"""Run the bounded Linux Direct Panel Driver v1 demonstration."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time

from .device import HongtaiPanel, validate_resolution
from .direct import stream_demo
from .discovery import resolve_panel_path
from .rendering import encode_jpeg, render_test_pattern


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stream the verified 480x320 Hongtai Linux demo"
    )
    parser.add_argument(
        "--device",
        default=None,
        help="serial path; omit to prefer by-id and then exact 33c3:7802 ttyACM",
    )
    parser.add_argument(
        "--frame-interval",
        type=float,
        default=5.0,
        help="seconds between complete JPEG frames (default: 5)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="optional bounded run time in seconds; otherwise run until Ctrl+C",
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=None,
        help="optional backlight level from 0 through 100",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    try:
        path = resolve_panel_path(args.device)
        logging.info("Opening supported panel at %s", path)
        with HongtaiPanel(path) as panel:
            info = panel.query_device_info()
            width, height = validate_resolution(info)
            logging.info(
                "Verified %s firmware %s at %dx%d",
                info.model or "unknown model",
                info.version or "unknown version",
                width,
                height,
            )

            def provide_frame() -> bytes:
                status = time.strftime("%Y-%m-%d %H:%M:%S")
                image = render_test_pattern(
                    width,
                    height,
                    model=info.model or "model not reported",
                    status=status,
                )
                return encode_jpeg(image, quality=80)

            stream_demo(
                panel,
                info,
                provide_frame,
                stop_event,
                frame_interval=args.frame_interval,
                duration=args.duration,
                brightness=args.brightness,
            )
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logging.error("Panel driver stopped: %s", exc)
        return 1

    logging.info("Panel serial port closed cleanly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
