"""Run the experimental, unsupported foreground Hongtai display service."""

from __future__ import annotations

import argparse
import logging
import signal
import threading

from .cli_image import prepare_jpeg
from .config import load_config, load_config_if_present
from .layout import LiveLayout, default_layout_path
from .layout_renderer import render_layout
from .metrics import SystemMetricsCollector
from .rendering import encode_jpeg, render_test_pattern
from .service import DynamicDisplayService, StaticDisplayService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Experimental unsupported display service; reconnect is disabled by "
            "default and is outside accepted v1"
        )
    )
    parser.add_argument("--config", help="JSON configuration path")
    parser.add_argument("--layout", default=None, help="dashboard layout JSON path")
    parser.add_argument("--device", default=None, help="serial path; omit for auto-discovery")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--image", default=None, help="image to display")
    source.add_argument("--dashboard", action="store_true", help="show live system metrics")
    source.add_argument("--test-pattern", action="store_true", help="show the test pattern")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--quality", type=int, default=None)
    parser.add_argument("--update-interval", type=float, default=None)
    parser.add_argument("--reconnect-delay", type=float, default=None)
    parser.add_argument(
        "--reconnect",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="retry after panel failures; disabled by default for firmware safety",
    )
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base = load_config(args.config) if args.config else load_config_if_present()
        mode = (
            "image"
            if args.image
            else "dashboard"
            if args.dashboard
            else "test_pattern"
            if args.test_pattern
            else None
        )
        config = base.with_overrides(
            mode=mode,
            image_path=args.image,
            layout_path=args.layout,
            device_path=args.device,
            width=args.width,
            height=args.height,
            jpeg_quality=args.quality,
            update_interval=args.update_interval,
            reconnect_delay=args.reconnect_delay,
            reconnect_enabled=args.reconnect,
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if config.mode == "dashboard":
        collector = SystemMetricsCollector()
        live_layout = LiveLayout(config.layout_path or default_layout_path())

        def provide_dashboard() -> bytes:
            metrics = collector.collect()
            return encode_jpeg(
                render_layout(live_layout.get(), metrics),
                config.jpeg_quality,
            )

        service = DynamicDisplayService(
            provide_dashboard,
            device_path=config.device_path,
            frame_interval=config.update_interval,
            reconnect_delay=config.reconnect_delay,
            reconnect=config.reconnect_enabled,
        )
    elif config.mode == "image":
        assert config.image_path is not None
        jpeg = prepare_jpeg(
            config.image_path, config.width, config.height, config.jpeg_quality
        )
        service = StaticDisplayService(
            jpeg,
            device_path=config.device_path,
            reconnect_delay=config.reconnect_delay,
            reconnect=config.reconnect_enabled,
        )
    else:
        jpeg = encode_jpeg(
            render_test_pattern(config.width, config.height), config.jpeg_quality
        )
        service = StaticDisplayService(
            jpeg,
            device_path=config.device_path,
            reconnect_delay=config.reconnect_delay,
            reconnect=config.reconnect_enabled,
        )

    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    service.run(stop_event)
    logging.info("Hongtai display service stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
