"""Persistent display runners with firmware-safe failure behavior."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from .diagnostics import ReplyCapture
from .device import HongtaiPanel
from .discovery import resolve_panel_path
from .protocol import ProtocolError

LOGGER = logging.getLogger(__name__)


class StaticDisplayService:
    """Keep one JPEG visible, reconnecting when the serial device disappears."""

    def __init__(
        self,
        jpeg: bytes,
        *,
        device_path: str | None = None,
        refresh_interval: float = 1.4,
        reconnect_delay: float = 2.0,
        reconnect: bool = True,
        panel_factory: Callable[[str], HongtaiPanel] = HongtaiPanel,
        path_resolver: Callable[[str | None], str] = resolve_panel_path,
    ) -> None:
        if refresh_interval <= 0:
            raise ValueError("refresh_interval must be positive")
        if reconnect_delay < 0:
            raise ValueError("reconnect_delay cannot be negative")
        self.jpeg = jpeg
        self.device_path = device_path
        self.refresh_interval = refresh_interval
        self.reconnect_delay = reconnect_delay
        self.reconnect = reconnect
        self.panel_factory = panel_factory
        self.path_resolver = path_resolver

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                path = self.path_resolver(self.device_path)
                LOGGER.info("Connecting to Hongtai panel at %s", path)
                with self.panel_factory(path) as panel:
                    panel.send_jpeg(self.jpeg)
                    LOGGER.info("Display active; sending refresh commands")
                    while not stop_event.wait(self.refresh_interval):
                        panel.refresh()
            except (OSError, RuntimeError, TimeoutError, ProtocolError) as exc:
                if stop_event.is_set():
                    break
                LOGGER.warning("Panel unavailable: %s", exc)
                if not self.reconnect:
                    stop_event.set()
                    break
                stop_event.wait(self.reconnect_delay)


class DynamicDisplayService:
    """Send changing JPEGs while maintaining the pipeline between frames.

    Full JPEG uploads are deliberately paced independently from inexpensive
    refresh commands. This reduces sustained decoder and USB load while still
    satisfying firmware 3.2's roughly 1.5-second live-pipeline timeout.
    """

    def __init__(
        self,
        frame_provider: Callable[[], bytes],
        *,
        device_path: str | None = None,
        frame_interval: float = 30.0,
        refresh_interval: float = 1.0,
        reconnect_delay: float = 2.0,
        reconnect: bool = True,
        reply_capture: ReplyCapture | None = None,
        operation_observer: Callable[[str, float, int | None], None] | None = None,
        health_check: Callable[[], None] | None = None,
        session_limit: float | None = None,
        panel_factory: Callable[[str], HongtaiPanel] = HongtaiPanel,
        path_resolver: Callable[[str | None], str] = resolve_panel_path,
    ) -> None:
        if not 0 < frame_interval <= 60:
            raise ValueError("frame_interval must be greater than zero and at most 60")
        if not 0 < refresh_interval <= 1.4:
            raise ValueError(
                "refresh_interval must be greater than zero and at most 1.4"
            )
        if reconnect_delay < 0:
            raise ValueError("reconnect_delay cannot be negative")
        if session_limit is not None and not 0 < session_limit <= 1800:
            raise ValueError("session_limit must be greater than zero and at most 1800")
        self.frame_provider = frame_provider
        self.device_path = device_path
        self.frame_interval = frame_interval
        self.refresh_interval = refresh_interval
        self.reconnect_delay = reconnect_delay
        self.reconnect = reconnect
        self.reply_capture = reply_capture
        self.operation_observer = operation_observer
        self.health_check = health_check
        self.session_limit = session_limit
        self.panel_factory = panel_factory
        self.path_resolver = path_resolver
        self.last_error: BaseException | None = None

    def _observe(self, label: str, started_at: float, jpeg_size: int | None) -> None:
        if self.operation_observer is not None:
            self.operation_observer(label, time.monotonic() - started_at, jpeg_size)

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                path = self.path_resolver(self.device_path)
                LOGGER.info("Connecting to Hongtai panel at %s", path)
                with self.panel_factory(path) as panel:
                    LOGGER.info("Dynamic display active")
                    if self.health_check is not None:
                        self.health_check()
                    jpeg = self.frame_provider()
                    operation_started = time.monotonic()
                    panel.send_jpeg(jpeg, reset=True, wake=True, commit=True)
                    self._observe("first_frame", operation_started, len(jpeg))
                    if self.reply_capture is not None:
                        self.reply_capture.poll(panel, "first_frame")
                    session_deadline = (
                        time.monotonic() + self.session_limit
                        if self.session_limit is not None
                        else None
                    )
                    next_frame_at = time.monotonic() + self.frame_interval
                    next_refresh_at = time.monotonic() + self.refresh_interval
                    while not stop_event.is_set():
                        now = time.monotonic()
                        deadline = min(next_frame_at, next_refresh_at)
                        if session_deadline is not None:
                            deadline = min(deadline, session_deadline)
                        if stop_event.wait(max(0.0, deadline - now)):
                            break
                        now = time.monotonic()
                        if self.health_check is not None:
                            self.health_check()
                        if session_deadline is not None and now >= session_deadline:
                            LOGGER.info(
                                "Diagnostic session limit reached after %.1f seconds",
                                self.session_limit,
                            )
                            stop_event.set()
                            break
                        if now >= next_frame_at:
                            jpeg = self.frame_provider()
                            operation_started = time.monotonic()
                            panel.send_jpeg(
                                jpeg,
                                reset=False,
                                wake=False,
                                commit=True,
                            )
                            self._observe("frame", operation_started, len(jpeg))
                            if self.reply_capture is not None:
                                self.reply_capture.poll(panel, "frame")
                            next_frame_at = time.monotonic() + self.frame_interval
                            next_refresh_at = time.monotonic() + self.refresh_interval
                        elif now >= next_refresh_at:
                            operation_started = time.monotonic()
                            panel.refresh()
                            self._observe("refresh", operation_started, None)
                            if self.reply_capture is not None:
                                self.reply_capture.poll(panel, "refresh")
                            next_refresh_at = time.monotonic() + self.refresh_interval
            except (OSError, RuntimeError, TimeoutError, ProtocolError) as exc:
                self.last_error = exc
                if stop_event.is_set():
                    break
                LOGGER.warning("Panel unavailable: %s", exc)
                if not self.reconnect:
                    stop_event.set()
                    break
                stop_event.wait(self.reconnect_delay)
