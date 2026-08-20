"""Image rendering helpers shared by command-line tools and the future UI."""

from __future__ import annotations

from io import BytesIO

from .protocol import MAX_JPEG_BYTES, ProtocolError


def fit_panel_image(image, width: int = 480, height: int = 320):
    """Crop and resize a Pillow image to fill the panel without distortion."""
    if width <= 0 or height <= 0:
        raise ValueError("panel width and height must be positive")
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("image fitting requires Pillow") from exc
    return ImageOps.fit(
        image.convert("RGB"),
        (width, height),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


def encode_jpeg(image, quality: int = 85, min_quality: int = 30) -> bytes:
    """Encode a Pillow image within the verified panel's JPEG size budget."""
    if not 1 <= min_quality <= quality <= 95:
        raise ValueError("quality must satisfy 1 <= min_quality <= quality <= 95")

    rgb = image.convert("RGB")
    for current_quality in range(quality, min_quality - 1, -5):
        output = BytesIO()
        rgb.save(output, "JPEG", quality=current_quality, optimize=True)
        jpeg = output.getvalue()
        if len(jpeg) <= MAX_JPEG_BYTES:
            return jpeg
    raise ProtocolError(
        f"image cannot fit the {MAX_JPEG_BYTES}-byte limit at quality {min_quality}"
    )


def render_test_pattern(
    width: int = 480,
    height: int = 320,
    *,
    model: str = "TXW818-ST7796-3.5inch-hor",
    status: str | None = None,
):
    """Return a Pillow image that makes geometry and color errors obvious."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("test-pattern rendering requires Pillow") from exc

    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    colors = ["#ef4444", "#f59e0b", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7"]
    bar_height = max(18, height // 10)
    bar_width = width / len(colors)
    for index, color in enumerate(colors):
        left = round(index * bar_width)
        right = round((index + 1) * bar_width)
        draw.rectangle((left, 0, right, bar_height), fill=color)

    margin = max(10, width // 32)
    draw.rectangle(
        (margin, bar_height + margin, width - margin - 1, height - margin - 1),
        outline="#e5e7eb",
        width=max(2, width // 160),
    )

    marker = max(24, min(width, height) // 7)
    corners = (
        ((0, 0, marker, marker), "#ef4444", "TL"),
        ((width - marker, 0, width - 1, marker), "#22c55e", "TR"),
        ((0, height - marker, marker, height - 1), "#3b82f6", "BL"),
        (
            (width - marker, height - marker, width - 1, height - 1),
            "#f59e0b",
            "BR",
        ),
    )

    def font(size: int, bold: bool = False):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        try:
            return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
        except OSError:
            return ImageFont.load_default()

    title_font = font(max(22, width // 12), bold=True)
    body_font = font(max(16, width // 22))
    small_font = font(max(12, width // 30))

    for bounds, color, label in corners:
        draw.rectangle(bounds, fill=color)
        label_box = draw.textbbox((0, 0), label, font=small_font)
        label_width = label_box[2] - label_box[0]
        label_height = label_box[3] - label_box[1]
        left, top, right, bottom = bounds
        draw.text(
            (
                left + (right - left - label_width) // 2,
                top + (bottom - top - label_height) // 2,
            ),
            label,
            fill="#ffffff",
            font=small_font,
        )

    lines = [
        ("HONGTAI LINUX", title_font, "#f9fafb"),
        ("LIVE PROTOCOL TEST", body_font, "#67e8f9"),
        (f"{width} x {height} | Linux | USB 33c3:7802", small_font, "#d1d5db"),
        (model, small_font, "#c4b5fd"),
    ]
    if status:
        lines.append((status, small_font, "#fde68a"))
    heights = [draw.textbbox((0, 0), text, font=fnt)[3] for text, fnt, _ in lines]
    total_height = sum(heights) + max(8, height // 40) * (len(lines) - 1)
    y = bar_height + (height - bar_height - total_height) // 2
    for (text, fnt, color), text_height in zip(lines, heights):
        box = draw.textbbox((0, 0), text, font=fnt)
        text_width = box[2] - box[0]
        draw.text(((width - text_width) // 2, y), text, fill=color, font=fnt)
        y += text_height + max(8, height // 40)

    return image
