"""Bounded Linux-first driver loop for the verified front panel."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from .device import DeviceInfo, HongtaiPanel, validate_resolution

LOGGER = logging.getLogger(__name__)


def stream_demo(
    panel: HongtaiPanel,
    info: DeviceInfo,
    frame_provider: Callable[[], bytes],
    stop_event: threading.Event,
    *,
    frame_interval: float = 5.0,
    refresh_interval: float = 1.0,
    duration: float | None = None,
    brightness: int | None = None,
    brightness_update: Callable[[], int | None] | None = None,
) -> int:
    """Stream modest-rate demo frames until stopped, returning frames sent."""
    validate_resolution(info)
    if frame_interval <= 0:
        raise ValueError("frame_interval must be positive")
    if not 0 < refresh_interval <= 1.4:
        raise ValueError("refresh_interval must be greater than zero and at most 1.4")
    if duration is not None and duration <= 0:
        raise ValueError("duration must be positive")

    if brightness is not None:
        panel.set_brightness(brightness)

    panel.send_jpeg(frame_provider())
    frames_sent = 1
    started = time.monotonic()
    next_frame = started + frame_interval
    next_refresh = started + refresh_interval
    deadline = None if duration is None else started + duration

    while not stop_event.is_set():
        wake_at = min(next_frame, next_refresh)
        if deadline is not None:
            wake_at = min(wake_at, deadline)
        if stop_event.wait(max(0.0, wake_at - time.monotonic())):
            break

        now = time.monotonic()
        if deadline is not None and now >= deadline:
            break
        if brightness_update is not None:
            updated_brightness = brightness_update()
            if updated_brightness is not None:
                panel.set_brightness(updated_brightness)
        if now >= next_frame:
            panel.send_jpeg(
                frame_provider(), reset=False, wake=False, commit=True
            )
            frames_sent += 1
            now = time.monotonic()
            next_frame = now + frame_interval
            next_refresh = now + refresh_interval
        elif now >= next_refresh:
            panel.refresh()
            next_refresh = time.monotonic() + refresh_interval

    LOGGER.info("Demo stream stopped after %d frame(s)", frames_sent)
    return frames_sent
