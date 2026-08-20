"""Versioned, declarative panel layouts and safe live reloading."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
LAYOUT_VERSION = 1
WIDGET_KINDS = {"panel", "label", "clock", "value", "progress", "image"}
METRIC_SOURCES = {
    "cpu_percent",
    "cpu_temp_c",
    "memory_percent",
    "memory_used_gib",
    "memory_total_gib",
    "gpu_name",
    "gpu_percent",
    "gpu_temp_c",
    "gpu_memory_used_gib",
    "gpu_memory_total_gib",
}


@dataclass(frozen=True, slots=True)
class Widget:
    kind: str
    x: int
    y: int
    width: int
    height: int
    text: str | None = None
    source: str | None = None
    format: str | None = None
    missing: str = "--"
    font_size: int = 16
    bold: bool = False
    color: str = "#f8fafc"
    fill: str | None = None
    outline: str | None = None
    radius: int = 0
    stroke_width: int = 1
    align: str = "left"
    minimum: float = 0.0
    maximum: float = 100.0
    path: str | None = None
    fit: str = "contain"

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "Widget":
        expected = set(cls.__dataclass_fields__)
        unknown = set(values) - expected
        if unknown:
            raise ValueError(f"unknown widget fields: {', '.join(sorted(unknown))}")
        try:
            return cls(**values)
        except TypeError as exc:
            raise ValueError(f"invalid widget: {exc}") from exc

    def validated(self, canvas_width: int, canvas_height: int) -> "Widget":
        if self.kind not in WIDGET_KINDS:
            raise ValueError(f"unknown widget kind: {self.kind}")
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise ValueError(f"{self.kind} widget has invalid geometry")
        if self.x + self.width > canvas_width or self.y + self.height > canvas_height:
            raise ValueError(f"{self.kind} widget extends outside the canvas")
        if not 1 <= self.font_size <= 256:
            raise ValueError("font_size must be between 1 and 256")
        if self.align not in {"left", "center", "right"}:
            raise ValueError("align must be left, center, or right")
        if self.radius < 0 or self.stroke_width < 0:
            raise ValueError("radius and stroke_width cannot be negative")
        if self.kind == "label" and self.text is None:
            raise ValueError("label widget requires text")
        if self.kind in {"value", "progress"} and self.source not in METRIC_SOURCES:
            raise ValueError(f"{self.kind} widget has invalid metric source: {self.source}")
        if self.kind == "progress" and self.maximum <= self.minimum:
            raise ValueError("progress maximum must be greater than minimum")
        if self.kind == "image" and not self.path:
            raise ValueError("image widget requires path")
        if self.fit not in {"contain", "cover", "stretch"}:
            raise ValueError("image fit must be contain, cover, or stretch")
        return self


@dataclass(frozen=True, slots=True)
class Layout:
    version: int = LAYOUT_VERSION
    name: str = "Untitled layout"
    width: int = 480
    height: int = 320
    background: str = "#080d18"
    widgets: tuple[Widget, ...] = field(default_factory=tuple)
    asset_root: Path = field(default=Path("."), compare=False, repr=False)

    @classmethod
    def from_dict(
        cls, values: dict[str, Any], *, asset_root: str | Path = "."
    ) -> "Layout":
        expected = {"version", "name", "width", "height", "background", "widgets"}
        unknown = set(values) - expected
        if unknown:
            raise ValueError(f"unknown layout fields: {', '.join(sorted(unknown))}")
        raw_widgets = values.get("widgets", [])
        if not isinstance(raw_widgets, list):
            raise ValueError("layout widgets must be a JSON array")
        widgets: list[Widget] = []
        for index, item in enumerate(raw_widgets):
            if not isinstance(item, dict):
                raise ValueError(f"widget {index} must be a JSON object")
            try:
                widgets.append(Widget.from_dict(item))
            except ValueError as exc:
                raise ValueError(f"widget {index}: {exc}") from exc
        layout_values = {key: value for key, value in values.items() if key != "widgets"}
        try:
            layout = cls(
                **layout_values,
                widgets=tuple(widgets),
                asset_root=Path(asset_root).resolve(),
            )
        except TypeError as exc:
            raise ValueError(f"invalid layout: {exc}") from exc
        return layout.validated()

    def validated(self) -> "Layout":
        if self.version != LAYOUT_VERSION:
            raise ValueError(
                f"unsupported layout version {self.version}; expected {LAYOUT_VERSION}"
            )
        if not 1 <= self.width <= 4096 or not 1 <= self.height <= 4096:
            raise ValueError("layout width and height must be between 1 and 4096")
        for widget in self.widgets:
            widget.validated(self.width, self.height)
        return self


def load_layout(path: str | Path) -> Layout:
    layout_path = Path(path)
    try:
        values = json.loads(layout_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {layout_path}: {exc}") from exc
    if not isinstance(values, dict):
        raise ValueError(f"layout in {layout_path} must be a JSON object")
    return Layout.from_dict(values, asset_root=layout_path.parent)


def default_layout_path() -> Path:
    return Path(__file__).resolve().parent / "layouts" / "default-dashboard.json"


class LiveLayout:
    """Reload a saved layout after changes, retaining the last valid version."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._layout: Layout | None = None
        self._observed_mtime_ns: int | None = None

    def get(self) -> Layout:
        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            if self._layout is not None:
                return self._layout
            raise
        if self._layout is not None and mtime_ns == self._observed_mtime_ns:
            return self._layout
        self._observed_mtime_ns = mtime_ns
        try:
            candidate = load_layout(self.path)
        except (OSError, ValueError) as exc:
            if self._layout is None:
                raise
            LOGGER.warning("Layout reload rejected; retaining last valid layout: %s", exc)
            return self._layout
        self._layout = candidate
        LOGGER.info("Loaded layout %s from %s", candidate.name, self.path)
        return candidate
