"""480×320 starter dashboard renderer."""

from __future__ import annotations

from .metrics import SystemMetrics


def render_dashboard(metrics: SystemMetrics, width: int = 480, height: int = 320):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("dashboard rendering requires Pillow") from exc

    image = Image.new("RGB", (width, height), "#080d18")
    draw = ImageDraw.Draw(image)

    def font(size: int, bold: bool = False):
        filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(
                f"/usr/share/fonts/truetype/dejavu/{filename}", size
            )
        except OSError:
            return ImageFont.load_default()

    title_font = font(20, True)
    clock_font = font(24, True)
    label_font = font(15, True)
    value_font = font(31, True)
    small_font = font(13)

    draw.text((16, 10), "SYSTEM MONITOR", font=title_font, fill="#dbeafe")
    clock = metrics.captured_at.strftime("%H:%M:%S")
    clock_width = draw.textbbox((0, 0), clock, font=clock_font)[2]
    draw.text((width - clock_width - 16, 7), clock, font=clock_font, fill="#67e8f9")
    draw.line((16, 42, width - 16, 42), fill="#1e3a5f", width=2)

    gap = 12
    margin = 16
    card_width = (width - margin * 2 - gap) // 2
    card_top = 55
    card_height = 150

    _metric_card(
        draw,
        (margin, card_top, margin + card_width, card_top + card_height),
        "CPU",
        _percent(metrics.cpu_percent),
        _temperature(metrics.cpu_temp_c),
        metrics.cpu_percent,
        "#22d3ee",
        label_font,
        value_font,
        small_font,
    )
    _metric_card(
        draw,
        (
            margin + card_width + gap,
            card_top,
            width - margin,
            card_top + card_height,
        ),
        "GPU",
        _percent(metrics.gpu_percent),
        _temperature(metrics.gpu_temp_c),
        metrics.gpu_percent,
        "#a78bfa",
        label_font,
        value_font,
        small_font,
    )

    memory_top = 220
    draw.rounded_rectangle(
        (margin, memory_top, width - margin, height - 15),
        radius=12,
        fill="#111827",
        outline="#263449",
        width=2,
    )
    draw.text((30, memory_top + 14), "MEMORY", font=label_font, fill="#94a3b8")
    memory_text = _memory(metrics.memory_used_bytes, metrics.memory_total_bytes)
    text_width = draw.textbbox((0, 0), memory_text, font=label_font)[2]
    draw.text(
        (width - 30 - text_width, memory_top + 14),
        memory_text,
        font=label_font,
        fill="#f8fafc",
    )
    _progress_bar(
        draw,
        (30, memory_top + 48, width - 30, memory_top + 67),
        metrics.memory_percent,
        "#34d399",
    )
    percent_text = _percent(metrics.memory_percent)
    draw.text((30, memory_top + 70), percent_text, font=small_font, fill="#a7f3d0")
    gpu_label = metrics.gpu_name or "GPU telemetry unavailable"
    gpu_label = gpu_label if len(gpu_label) <= 34 else gpu_label[:31] + "..."
    label_width = draw.textbbox((0, 0), gpu_label, font=small_font)[2]
    draw.text(
        (width - 30 - label_width, memory_top + 70),
        gpu_label,
        font=small_font,
        fill="#94a3b8",
    )
    return image


def _metric_card(
    draw,
    bounds: tuple[int, int, int, int],
    label: str,
    percentage: str,
    temperature: str,
    value: float | None,
    accent: str,
    label_font,
    value_font,
    small_font,
) -> None:
    left, top, right, bottom = bounds
    draw.rounded_rectangle(bounds, radius=12, fill="#111827", outline="#263449", width=2)
    draw.text((left + 14, top + 13), label, font=label_font, fill=accent)
    temperature_width = draw.textbbox((0, 0), temperature, font=label_font)[2]
    draw.text(
        (right - 14 - temperature_width, top + 13),
        temperature,
        font=label_font,
        fill="#f8fafc",
    )
    draw.text((left + 14, top + 45), percentage, font=value_font, fill="#f8fafc")
    draw.text((left + 15, top + 83), "UTILIZATION", font=small_font, fill="#64748b")
    _progress_bar(draw, (left + 14, bottom - 34, right - 14, bottom - 16), value, accent)


def _progress_bar(draw, bounds, value: float | None, color: str) -> None:
    left, top, right, bottom = bounds
    draw.rounded_rectangle(bounds, radius=7, fill="#263449")
    if value is None:
        return
    ratio = max(0.0, min(100.0, value)) / 100.0
    if ratio > 0:
        filled_right = max(left + 6, round(left + (right - left) * ratio))
        draw.rounded_rectangle((left, top, filled_right, bottom), radius=7, fill=color)


def _percent(value: float | None) -> str:
    return "--%" if value is None else f"{value:.0f}%"


def _temperature(value: float | None) -> str:
    return "--°C" if value is None else f"{value:.0f}°C"


def _memory(used: int | None, total: int | None) -> str:
    if used is None or total is None:
        return "-- / -- GiB"
    gib = 1024**3
    return f"{used / gib:.1f} / {total / gib:.1f} GiB"
