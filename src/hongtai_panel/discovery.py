"""Discovery of stable Linux device paths for Hongtai panels."""

from __future__ import annotations

import glob
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Callable

DEFAULT_PATTERNS = (
    "/dev/serial/by-id/*HONGTAI*",
    "/dev/serial/by-id/*Hongtai*",
    "/dev/serial/by-id/*hongtai*",
)
FALLBACK_PATTERN = "/dev/ttyACM*"
SUPPORTED_USB_ID = (0x33C3, 0x7802)


def read_usb_identity(
    device_path: str, *, tty_class: str = "/sys/class/tty"
) -> tuple[int, int] | None:
    """Read a tty's USB VID:PID from sysfs when Linux exposes it."""
    tty_name = os.path.basename(os.path.realpath(device_path))
    sys_device = Path(tty_class, tty_name, "device")
    try:
        current = sys_device.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return None

    for parent in (current, *current.parents):
        vendor_file = parent / "idVendor"
        product_file = parent / "idProduct"
        if not vendor_file.is_file() or not product_file.is_file():
            continue
        try:
            return (
                int(vendor_file.read_text(encoding="ascii").strip(), 16),
                int(product_file.read_text(encoding="ascii").strip(), 16),
            )
        except (OSError, ValueError):
            return None
    return None


def discover_panels(
    patterns: Iterable[str] = DEFAULT_PATTERNS,
    *,
    fallback_pattern: str = FALLBACK_PATTERN,
    identity_reader: Callable[[str], tuple[int, int] | None] = read_usb_identity,
) -> list[str]:
    """Find supported panels, preferring stable by-id links.

    A matching by-id name remains usable on systems where sysfs identity is not
    readable. The generic ``ttyACM`` fallback is accepted only when sysfs proves
    that its USB identity is exactly ``33c3:7802``.
    """
    stable: set[str] = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            if os.path.exists(path):
                identity = identity_reader(path)
                if identity in (None, SUPPORTED_USB_ID):
                    stable.add(path)
    if stable:
        return sorted(stable)

    fallback = {
        path
        for path in glob.glob(fallback_pattern)
        if os.path.exists(path) and identity_reader(path) == SUPPORTED_USB_ID
    }
    return sorted(fallback)


def resolve_panel_path(
    explicit_path: str | None = None,
    patterns: Iterable[str] = DEFAULT_PATTERNS,
    *,
    fallback_pattern: str = FALLBACK_PATTERN,
    identity_reader: Callable[[str], tuple[int, int] | None] = read_usb_identity,
) -> str:
    """Resolve one panel path, refusing ambiguous automatic selection."""
    if explicit_path:
        if not os.path.exists(explicit_path):
            raise FileNotFoundError(f"panel device does not exist: {explicit_path}")
        identity = identity_reader(explicit_path)
        if identity is not None and identity != SUPPORTED_USB_ID:
            vendor, product = identity
            raise RuntimeError(
                f"refusing USB {vendor:04x}:{product:04x} at {explicit_path}; "
                "expected 33c3:7802"
            )
        return explicit_path

    panels = discover_panels(
        patterns,
        fallback_pattern=fallback_pattern,
        identity_reader=identity_reader,
    )
    if not panels:
        raise FileNotFoundError(
            "no supported 33c3:7802 panel found under /dev/serial/by-id "
            "or /dev/ttyACM*"
        )
    if len(panels) > 1:
        joined = ", ".join(panels)
        raise RuntimeError(f"multiple Hongtai panels found; choose one explicitly: {joined}")
    return panels[0]
