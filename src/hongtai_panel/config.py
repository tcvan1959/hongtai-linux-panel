"""Validated saved configuration for the panel service."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

CONFIG_VERSION = 1
VALID_MODES = {"dashboard", "test_pattern", "image"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    version: int = CONFIG_VERSION
    mode: str = "dashboard"
    device_path: str | None = None
    image_path: str | None = None
    layout_path: str | None = None
    width: int = 480
    height: int = 320
    jpeg_quality: int = 55
    update_interval: float = 30.0
    reconnect_delay: float = 2.0
    reconnect_enabled: bool = False

    def validated(self) -> "AppConfig":
        if self.version != CONFIG_VERSION:
            raise ValueError(
                f"unsupported configuration version {self.version}; expected {CONFIG_VERSION}"
            )
        if self.mode not in VALID_MODES:
            raise ValueError(f"mode must be one of: {', '.join(sorted(VALID_MODES))}")
        if not 1 <= self.width <= 4096 or not 1 <= self.height <= 4096:
            raise ValueError("width and height must be between 1 and 4096")
        if not 30 <= self.jpeg_quality <= 95:
            raise ValueError("jpeg_quality must be between 30 and 95")
        if not 0 < self.update_interval <= 60:
            raise ValueError("update_interval must be greater than zero and at most 60")
        if self.reconnect_delay < 0:
            raise ValueError("reconnect_delay cannot be negative")
        if not isinstance(self.reconnect_enabled, bool):
            raise ValueError("reconnect_enabled must be true or false")
        if self.mode == "image" and not self.image_path:
            raise ValueError("image mode requires image_path")
        return self

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "AppConfig":
        expected = set(cls.__dataclass_fields__)
        unknown = set(values) - expected
        if unknown:
            raise ValueError(f"unknown configuration fields: {', '.join(sorted(unknown))}")
        return cls(**values).validated()

    def with_overrides(self, **values: Any) -> "AppConfig":
        filtered = {key: value for key, value in values.items() if value is not None}
        return replace(self, **filtered).validated()


def default_config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "hongtai-linux-panel" / "config.json"


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {config_path}: {exc}") from exc
    if not isinstance(values, dict):
        raise ValueError(f"configuration in {config_path} must be a JSON object")
    return AppConfig.from_dict(values)


def load_config_if_present(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path) if path is not None else default_config_path()
    return load_config(config_path) if config_path.exists() else AppConfig().validated()


def save_config(config: AppConfig, path: str | Path) -> Path:
    config = config.validated()
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(asdict(config), indent=2, sort_keys=True) + "\n"
    config_path.write_text(content, encoding="utf-8")
    return config_path
