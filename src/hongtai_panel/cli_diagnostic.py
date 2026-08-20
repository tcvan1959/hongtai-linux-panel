"""Run one bounded live-stream diagnostic and report passive serial replies."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import threading
import time
from datetime import datetime, timezone

from .config import load_config, load_config_if_present
from .device import HongtaiPanel
from .diagnostics import HostHealthCheck, ReplyCapture, WriteCapture
from .layout import LiveLayout, default_layout_path
from .layout_renderer import render_layout
from .metrics import SystemMetricsCollector
from .rendering import encode_jpeg
from .service import DynamicDisplayService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded Hongtai reply-capture diagnostic"
    )
    parser.add_argument("--config", help="JSON configuration path")
    parser.add_argument("--layout", help="dashboard layout JSON path")
    parser.add_argument("--device", help="serial path; omit for auto-discovery")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--frame-interval", type=float, default=5.0)
    parser.add_argument("--quality", type=int, default=55)
    parser.add_argument(
        "--kernel-usb-path",
        help="fail on new kernel messages for this USB path (for example 9-9)",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.duration <= 1800:
        raise SystemExit("Diagnostic duration must be between 1 and 1800 seconds")
    if not 0 < args.frame_interval <= 60:
        raise SystemExit("Frame interval must be greater than zero and at most 60 seconds")
    if not 30 <= args.quality <= 95:
        raise SystemExit("JPEG quality must be between 30 and 95")
    try:
        config = load_config(args.config) if args.config else load_config_if_present()
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    collector = SystemMetricsCollector()
    live_layout = LiveLayout(args.layout or config.layout_path or default_layout_path())

    def provide_dashboard() -> bytes:
        return encode_jpeg(
            render_layout(live_layout.get(), collector.collect()),
            quality=args.quality,
        )

    replies = ReplyCapture()
    writes = WriteCapture()
    operations: list[dict[str, object]] = []

    class BoundedDiagnosticPanel(HongtaiPanel):
        """Use a shorter fail-stop ceiling without changing normal driver policy."""

        def _write_all(self, data: bytes, timeout: float = 5.0) -> None:
            started = time.monotonic()
            error: BaseException | None = None
            try:
                super()._write_all(data, timeout=min(timeout, 0.75))
            except BaseException as exc:
                error = exc
                raise
            finally:
                writes.record(len(data), time.monotonic() - started, error)

    def observe_operation(label: str, duration: float, jpeg_size: int | None) -> None:
        operations.append(
            {
                "label": label,
                "duration_seconds": duration,
                "jpeg_size": jpeg_size,
            }
        )

    service = DynamicDisplayService(
        provide_dashboard,
        device_path=args.device or config.device_path,
        frame_interval=args.frame_interval,
        refresh_interval=1.0,
        reconnect=False,
        reply_capture=replies,
        operation_observer=observe_operation,
        health_check=(
            HostHealthCheck(
                args.device or config.device_path,
                args.kernel_usb_path,
            )
            if args.kernel_usb_path and (args.device or config.device_path)
            else None
        ),
        session_limit=args.duration,
        panel_factory=lambda path: BoundedDiagnosticPanel(path),
    )
    stop_event = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    started_wall = datetime.now(timezone.utc)
    started_monotonic = time.monotonic()
    service.run(stop_event)
    elapsed = time.monotonic() - started_monotonic
    ended_wall = datetime.now(timezone.utc)
    replies.finish()
    jpeg_sizes = [
        int(operation["jpeg_size"])
        for operation in operations
        if operation["jpeg_size"] is not None
    ]
    operation_summary: dict[str, dict[str, float | int]] = {}
    for label in ("first_frame", "frame", "refresh"):
        durations = sorted(
            float(operation["duration_seconds"])
            for operation in operations
            if operation["label"] == label
        )
        if not durations:
            continue
        p95_index = min(len(durations) - 1, round((len(durations) - 1) * 0.95))
        operation_summary[label] = {
            "count": len(durations),
            "min_seconds": durations[0],
            "median_seconds": durations[len(durations) // 2],
            "p95_seconds": durations[p95_index],
            "max_seconds": durations[-1],
        }
    result = {
        "start_utc": started_wall.isoformat(),
        "end_utc": ended_wall.isoformat(),
        "elapsed_seconds": elapsed,
        "requested_duration_seconds": args.duration,
        "frame_interval_seconds": args.frame_interval,
        "keepalive_interval_seconds": 1.0,
        "frame_count": len(jpeg_sizes),
        "keepalive_count": sum(
            operation["label"] == "refresh" for operation in operations
        ),
        "jpeg_size_min": min(jpeg_sizes) if jpeg_sizes else None,
        "jpeg_size_max": max(jpeg_sizes) if jpeg_sizes else None,
        "operation_latency": operation_summary,
        "writes": writes.summary(),
        "replies": replies.summary(),
        "failure": (
            None
            if service.last_error is None
            else f"{type(service.last_error).__name__}: {service.last_error}"
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if service.last_error is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
