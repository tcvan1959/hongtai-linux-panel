"""Foreground controller for the local Panel Control App v1."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .device import (
    DeviceInfo,
    HongtaiPanel,
    validate_brightness,
    validate_resolution,
)
from .direct import stream_demo
from .discovery import resolve_panel_path
from .layout import LiveLayout, default_layout_path
from .layout_renderer import render_layout
from .media import (
    ensure_private_media_dir,
    list_private_media,
    load_private_media,
    prepare_still_image,
)
from .metrics import SystemMetricsCollector
from .rendering import encode_jpeg, render_test_pattern

LAYOUTS = {
    "orientation": "Orientation test",
    "dashboard": "Starter dashboard",
    "image": "Selected image",
}


class PanelController:
    """Own panel state and exactly one foreground streaming worker."""

    def __init__(
        self,
        *,
        device_path: str | None = None,
        layout_path: str | Path | None = None,
        media_dir: str | Path | None = None,
        frame_interval: float = 5.0,
        refresh_interval: float = 1.0,
        panel_factory: Callable[[str], HongtaiPanel] = HongtaiPanel,
        path_resolver: Callable[[str | None], str] = resolve_panel_path,
        frame_factory: Callable[[str, DeviceInfo], bytes] | None = None,
    ) -> None:
        self.device_path = device_path
        self.layout_path = Path(layout_path or default_layout_path())
        self.media_dir = ensure_private_media_dir(media_dir)
        self.frame_interval = frame_interval
        self.refresh_interval = refresh_interval
        self.panel_factory = panel_factory
        self.path_resolver = path_resolver
        self._external_frame_factory = frame_factory
        self._live_layout = LiveLayout(self.layout_path)
        self._metrics = SystemMetricsCollector()
        self._lock = threading.RLock()
        self._operation_lock = threading.RLock()
        self._stop_event: threading.Event | None = None
        self._worker: threading.Thread | None = None
        self._brightness_updates: queue.SimpleQueue[int] = queue.SimpleQueue()
        self._state = "disconnected"
        self._path: str | None = None
        self._info: DeviceInfo | None = None
        self._brightness: int | None = None
        self._layout = "orientation"
        self._selected_image: bytes | None = None
        self._selected_image_name: str | None = None
        self._selected_image_source: str | None = None
        self._error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            info = self._info
            return {
                "state": self._state,
                "path": self._path,
                "model": info.model if info else None,
                "firmware": info.version if info else None,
                "width": info.width if info else None,
                "height": info.height if info else None,
                "brightness": self._brightness,
                "layout": self._layout,
                "layout_name": LAYOUTS[self._layout],
                "layouts": LAYOUTS,
                "selected_image": self._selected_image_name,
                "selected_image_source": self._selected_image_source,
                "can_display_image": (
                    self._selected_image is not None
                    and self._path is not None
                    and self._state not in {"starting", "streaming", "restarting"}
                ),
                "error": self._error,
                "can_restore_default": (
                    self._state == "stopped"
                    and self._path is not None
                    and info is not None
                    and (self._worker is None or not self._worker.is_alive())
                ),
            }

    def detect(self) -> dict[str, Any]:
        with self._operation_lock:
            if self._worker is not None and self._worker.is_alive():
                return self.snapshot()
            try:
                path = self.path_resolver(self.device_path)
                with self.panel_factory(path) as panel:
                    info = panel.query_device_info()
                validate_resolution(info)
                with self._lock:
                    self._path = path
                    self._info = info
                    self._brightness = info.brightness
                    self._state = "detected"
                    self._error = None
                return self.snapshot()
            except Exception as exc:
                self._record_error(exc)
                raise

    def start(
        self, layout: str = "orientation", brightness: int | None = None
    ) -> dict[str, Any]:
        if layout not in LAYOUTS:
            raise ValueError(f"unknown built-in layout: {layout}")
        if layout == "image" and self._selected_image is None:
            raise RuntimeError("choose a PNG or JPEG image before displaying it")
        if brightness is not None:
            validate_brightness(brightness)
        with self._operation_lock:
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("the panel is already streaming")
            if self._info is None or self._path is None:
                self.detect()
            assert self._path is not None
            assert self._info is not None
            selected_brightness = (
                brightness if brightness is not None else self._brightness
            )
            self._stop_event = threading.Event()
            self._brightness_updates = queue.SimpleQueue()
            with self._lock:
                self._layout = layout
                self._brightness = selected_brightness
                self._state = "starting"
                self._error = None
            worker = threading.Thread(
                target=self._stream_worker,
                args=(self._path, layout, selected_brightness, self._stop_event),
                name="hongtai-panel-stream",
                daemon=True,
            )
            self._worker = worker
            worker.start()
            return self.snapshot()

    def stop(self, timeout: float = 6.0) -> dict[str, Any]:
        with self._operation_lock:
            worker = self._worker
            stop_event = self._stop_event
            if worker is None or not worker.is_alive():
                with self._lock:
                    if self._state != "error":
                        self._state = "stopped" if self._info else "disconnected"
                return self.snapshot()
            assert stop_event is not None
            stop_event.set()
            worker.join(timeout)
            if worker.is_alive():
                error = RuntimeError("panel stream did not stop cleanly")
                self._record_error(error)
                raise error
            with self._lock:
                if self._state != "error":
                    self._state = "stopped"
            return self.snapshot()

    def set_brightness(self, percent: int) -> dict[str, Any]:
        validate_brightness(percent)
        with self._operation_lock:
            worker = self._worker
            if worker is not None and worker.is_alive():
                self._brightness_updates.put(percent)
                with self._lock:
                    self._brightness = percent
                    self._error = None
                return self.snapshot()
            if self._path is None or self._info is None:
                raise RuntimeError("detect the panel before changing brightness")
            try:
                with self.panel_factory(self._path) as panel:
                    panel.set_brightness(percent)
                with self._lock:
                    self._brightness = percent
                    self._error = None
                return self.snapshot()
            except Exception as exc:
                self._record_error(exc)
                raise

    def restore_default_display(self) -> dict[str, Any]:
        """Restart one stopped panel once, leaving re-detection to the user."""
        with self._operation_lock:
            worker = self._worker
            if worker is not None and worker.is_alive():
                raise RuntimeError("stop the live display before restarting the panel")
            with self._lock:
                if self._state != "stopped" or self._path is None or self._info is None:
                    raise RuntimeError(
                        "the display must be fully stopped before restoring the default"
                    )
                path = self._path
                self._state = "restarting"
                self._error = None
            try:
                with self.panel_factory(path) as panel:
                    panel.restart_panel()
                with self._lock:
                    # The verified board restart invalidates the old tty identity.
                    # Do not resolve, reopen, or query here; Detect panel is manual.
                    self._path = None
                    self._info = None
                    self._brightness = None
                return self.snapshot()
            except Exception as exc:
                self._record_error(exc)
                raise

    def preview(self, layout: str) -> bytes:
        if layout not in LAYOUTS:
            raise ValueError(f"unknown built-in layout: {layout}")
        with self._lock:
            info = self._info or DeviceInfo(
                None,
                None,
                "TXW818-ST7796-3.5inch-hor",
                "3.2",
                480,
                320,
                None,
                0,
                None,
                {},
            )
        return self._make_frame(layout, info)

    def media_library(self) -> dict[str, Any]:
        """Return a privacy-safe view of the local media library."""
        return {
            "directory": "display_media/local",
            "files": list_private_media(self.media_dir),
            "selected_image": self._selected_image_name,
            "selected_image_source": self._selected_image_source,
        }

    def select_library_image(self, name: str) -> dict[str, Any]:
        """Select one file from the private media folder without streaming."""
        with self._operation_lock:
            self._ensure_media_selection_allowed()
            safe_name, jpeg = load_private_media(self.media_dir, name)
            self._set_selected_image(safe_name, jpeg, "private library")
            return self.snapshot()

    def select_uploaded_image(self, name: str, data: bytes) -> dict[str, Any]:
        """Select browser-provided image bytes in memory without storing them."""
        with self._operation_lock:
            self._ensure_media_selection_allowed()
            jpeg = prepare_still_image(data, name)
            self._set_selected_image(Path(name).name, jpeg, "chosen file")
            return self.snapshot()

    def close(self) -> None:
        self.stop()

    def _stream_worker(
        self,
        path: str,
        layout: str,
        brightness: int | None,
        stop_event: threading.Event,
    ) -> None:
        try:
            with self.panel_factory(path) as panel:
                info = panel.query_device_info()
                validate_resolution(info)
                with self._lock:
                    self._info = info
                    self._state = "streaming"
                    self._error = None
                stream_demo(
                    panel,
                    info,
                    lambda: self._make_frame(layout, info),
                    stop_event,
                    frame_interval=self.frame_interval,
                    refresh_interval=self.refresh_interval,
                    brightness=brightness,
                    brightness_update=self._next_brightness,
                )
            with self._lock:
                if self._state != "error":
                    self._state = "stopped"
        except Exception as exc:
            self._record_error(exc)

    def _next_brightness(self) -> int | None:
        latest: int | None = None
        while True:
            try:
                latest = self._brightness_updates.get_nowait()
            except queue.Empty:
                return latest

    def _make_frame(self, layout: str, info: DeviceInfo) -> bytes:
        if self._external_frame_factory is not None:
            return self._external_frame_factory(layout, info)
        if layout == "image":
            with self._lock:
                if self._selected_image is None:
                    raise RuntimeError("choose a PNG or JPEG image before displaying it")
                return self._selected_image
        if layout == "orientation":
            image = render_test_pattern(
                480,
                320,
                model=info.model or "model not reported",
                status=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            image = render_layout(self._live_layout.get(), self._metrics.collect())
        return encode_jpeg(image, quality=80)

    def _ensure_media_selection_allowed(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            raise RuntimeError("stop the live display before choosing another image")
        if self._state == "restarting":
            raise RuntimeError("wait for the panel restart before choosing an image")

    def _set_selected_image(self, name: str, jpeg: bytes, source: str) -> None:
        with self._lock:
            self._selected_image_name = name
            self._selected_image = jpeg
            self._selected_image_source = source
            self._layout = "image"
            self._error = None

    def _record_error(self, exc: Exception) -> None:
        with self._lock:
            self._state = "error"
            self._error = str(exc) or exc.__class__.__name__
