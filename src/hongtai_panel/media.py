"""Private still-image selection and panel-safe preparation."""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from .rendering import encode_jpeg, fit_panel_image

SUPPORTED_MEDIA_FORMATS = {"JPEG", "PNG"}
SUPPORTED_MEDIA_SUFFIXES = {".jpeg", ".jpg", ".png"}
MAX_MEDIA_BYTES = 16 * 1024 * 1024
MAX_MEDIA_PIXELS = 40_000_000


def default_private_media_dir() -> Path:
    """Return the checkout media folder, or a private user-data folder installed."""
    project_root = Path(__file__).resolve().parents[2]
    if (project_root / "pyproject.toml").is_file():
        return project_root / "display_media" / "local"
    data_root = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    return data_root / "hongtai-linux-panel" / "media"


def ensure_private_media_dir(path: str | Path | None = None) -> Path:
    directory = Path(path) if path is not None else default_private_media_dir()
    directory = directory.expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def list_private_media(path: str | Path) -> list[str]:
    """List supported direct-child files without following symlinks."""
    directory = ensure_private_media_dir(path)
    return sorted(
        (
            item.name
            for item in directory.iterdir()
            if item.is_file()
            and not item.is_symlink()
            and item.suffix.lower() in SUPPORTED_MEDIA_SUFFIXES
        ),
        key=str.casefold,
    )


def load_private_media(path: str | Path, name: str) -> tuple[str, bytes]:
    """Load one direct-child private-media file and prepare it for the panel."""
    safe_name = _safe_name(name)
    directory = ensure_private_media_dir(path)
    selected = directory / safe_name
    if selected.is_symlink() or not selected.is_file():
        raise FileNotFoundError(f"private image not found: {safe_name}")
    try:
        size = selected.stat().st_size
        if size > MAX_MEDIA_BYTES:
            raise ValueError(f"image exceeds the {MAX_MEDIA_BYTES}-byte input limit")
        data = selected.read_bytes()
    except OSError as exc:
        raise OSError(f"cannot read private image {safe_name}: {exc}") from exc
    return safe_name, prepare_still_image(data, safe_name)


def prepare_still_image(
    data: bytes,
    name: str,
    *,
    width: int = 480,
    height: int = 320,
    quality: int = 80,
) -> bytes:
    """Validate one PNG/JPEG and return a fitted, bounded panel JPEG."""
    safe_name = _safe_name(name)
    if Path(safe_name).suffix.lower() not in SUPPORTED_MEDIA_SUFFIXES:
        raise ValueError("only PNG and JPEG/JPG still images are supported")
    if not data:
        raise ValueError("selected image is empty")
    if len(data) > MAX_MEDIA_BYTES:
        raise ValueError(f"image exceeds the {MAX_MEDIA_BYTES}-byte input limit")
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("media-library image support requires Pillow") from exc

    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in SUPPORTED_MEDIA_FORMATS:
                raise ValueError("only PNG and JPEG/JPG still images are supported")
            if getattr(source, "n_frames", 1) != 1:
                raise ValueError("animated images are not supported")
            if source.width * source.height > MAX_MEDIA_PIXELS:
                raise ValueError("image dimensions exceed the safe pixel limit")
            source.load()
            fitted = fit_panel_image(source, width, height)
    except UnidentifiedImageError as exc:
        raise ValueError("selected file is not a readable PNG or JPEG image") from exc
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"selected image cannot be decoded: {exc}") from exc
    return encode_jpeg(fitted, quality=quality)


def _safe_name(name: str) -> str:
    if not isinstance(name, str):
        raise TypeError("image name must be text")
    cleaned = name.strip()
    if not cleaned or Path(cleaned).name != cleaned or cleaned in {".", ".."}:
        raise ValueError("image name must be a single filename")
    return cleaned
