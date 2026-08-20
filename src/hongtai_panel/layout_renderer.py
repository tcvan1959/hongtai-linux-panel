"""Render declarative layouts into Pillow images."""

from __future__ import annotations

from pathlib import Path

from .layout import Layout, Widget
from .metrics import SystemMetrics


def render_layout(layout: Layout, metrics: SystemMetrics):
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as exc:
        raise RuntimeError("layout rendering requires Pillow") from exc

    image = Image.new("RGB", (layout.width, layout.height), layout.background)
    draw = ImageDraw.Draw(image)
    values = metric_values(metrics)

    def font(widget: Widget):
        filename = "DejaVuSans-Bold.ttf" if widget.bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(
                f"/usr/share/fonts/truetype/dejavu/{filename}", widget.font_size
            )
        except OSError:
            return ImageFont.load_default()

    for widget in layout.widgets:
        bounds = (
            widget.x,
            widget.y,
            widget.x + widget.width,
            widget.y + widget.height,
        )
        if widget.kind == "panel":
            draw.rounded_rectangle(
                bounds,
                radius=widget.radius,
                fill=widget.fill,
                outline=widget.outline,
                width=widget.stroke_width,
            )
        elif widget.kind == "label":
            _draw_text(draw, widget, widget.text or "", font(widget))
        elif widget.kind == "clock":
            _draw_text(
                draw,
                widget,
                metrics.captured_at.strftime(widget.format or "%H:%M:%S"),
                font(widget),
            )
        elif widget.kind == "value":
            raw = values.get(widget.source or "")
            text = _format_value(raw, widget.format, widget.missing)
            _draw_text(draw, widget, text, font(widget))
        elif widget.kind == "progress":
            raw = values.get(widget.source or "")
            _draw_progress(draw, widget, raw)
        elif widget.kind == "image":
            assert widget.path is not None
            asset_path = Path(widget.path)
            if not asset_path.is_absolute():
                asset_path = layout.asset_root / asset_path
            with Image.open(asset_path) as source:
                source = source.convert("RGB")
                if widget.fit == "cover":
                    rendered = ImageOps.fit(source, (widget.width, widget.height))
                elif widget.fit == "stretch":
                    rendered = source.resize((widget.width, widget.height))
                else:
                    rendered = ImageOps.contain(source, (widget.width, widget.height))
                offset = (
                    widget.x + (widget.width - rendered.width) // 2,
                    widget.y + (widget.height - rendered.height) // 2,
                )
                image.paste(rendered, offset)
    return image


def metric_values(metrics: SystemMetrics) -> dict[str, float | str | None]:
    gib = 1024**3
    return {
        "cpu_percent": metrics.cpu_percent,
        "cpu_temp_c": metrics.cpu_temp_c,
        "memory_percent": metrics.memory_percent,
        "memory_used_gib": _bytes_to_gib(metrics.memory_used_bytes, gib),
        "memory_total_gib": _bytes_to_gib(metrics.memory_total_bytes, gib),
        "gpu_name": metrics.gpu_name,
        "gpu_percent": metrics.gpu_percent,
        "gpu_temp_c": metrics.gpu_temp_c,
        "gpu_memory_used_gib": _bytes_to_gib(metrics.gpu_memory_used_bytes, gib),
        "gpu_memory_total_gib": _bytes_to_gib(metrics.gpu_memory_total_bytes, gib),
    }


def _bytes_to_gib(value: int | None, gib: int) -> float | None:
    return None if value is None else value / gib


def _format_value(value: float | str | None, format_spec: str | None, missing: str) -> str:
    if value is None:
        return missing
    if format_spec is None:
        return str(value)
    try:
        if "{value" in format_spec:
            return format_spec.format(value=value)
        return format(value, format_spec)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid value format {format_spec!r}: {exc}") from exc


def _draw_text(draw, widget: Widget, text: str, font) -> None:
    box = draw.textbbox((0, 0), text, font=font)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    if widget.align == "center":
        x = widget.x + (widget.width - text_width) // 2
    elif widget.align == "right":
        x = widget.x + widget.width - text_width
    else:
        x = widget.x
    y = widget.y + max(0, (widget.height - text_height) // 2 - box[1])
    draw.text((x, y), text, font=font, fill=widget.color)


def _draw_progress(draw, widget: Widget, value: float | str | None) -> None:
    bounds = (
        widget.x,
        widget.y,
        widget.x + widget.width,
        widget.y + widget.height,
    )
    draw.rounded_rectangle(bounds, radius=widget.radius, fill=widget.fill or "#263449")
    if not isinstance(value, (int, float)):
        return
    ratio = max(0.0, min(1.0, (value - widget.minimum) / (widget.maximum - widget.minimum)))
    if ratio <= 0:
        return
    right = max(widget.x + 2, round(widget.x + widget.width * ratio))
    draw.rounded_rectangle(
        (widget.x, widget.y, right, widget.y + widget.height),
        radius=widget.radius,
        fill=widget.color,
    )
