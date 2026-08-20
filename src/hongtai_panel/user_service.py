"""Generation and installation of the systemd user service."""

from __future__ import annotations

import subprocess
import sys
import shutil
from pathlib import Path

from .config import AppConfig, default_config_path, load_config, save_config
from .layout import default_layout_path

SERVICE_NAME = "hongtai-linux-panel.service"


def default_unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / SERVICE_NAME


def default_user_layout_path(config_path: str | Path | None = None) -> Path:
    config = Path(config_path) if config_path else default_config_path()
    return config.with_name("layout.json")


def _unit_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_user_unit(
    *,
    python_executable: str | Path = sys.executable,
    config_path: str | Path | None = None,
    source_root: str | Path | None = None,
) -> str:
    config = Path(config_path) if config_path is not None else default_config_path()
    source = (
        Path(source_root).resolve()
        if source_root is not None
        else Path(__file__).resolve().parents[1]
    )
    command = " ".join(
        [
            _unit_quote(str(Path(python_executable).resolve())),
            "-m",
            "hongtai_panel.cli_service",
            "--config",
            _unit_quote(str(config.resolve())),
        ]
    )
    return f"""[Unit]
Description=Hongtai Linux Panel display service
After=graphical-session.target

[Service]
Type=simple
Environment={_unit_quote(f"PYTHONPATH={source}")}
ExecStart={command}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""


def install_user_service(
    *,
    config: AppConfig | None = None,
    config_path: str | Path | None = None,
    unit_path: str | Path | None = None,
    python_executable: str | Path = sys.executable,
    source_root: str | Path | None = None,
    runner=subprocess.run,
) -> tuple[Path, Path]:
    resolved_config = Path(config_path) if config_path else default_config_path()
    resolved_unit = Path(unit_path) if unit_path else default_unit_path()
    selected_config = (
        config
        if config is not None
        else load_config(resolved_config)
        if resolved_config.exists()
        else AppConfig()
    )
    if selected_config.layout_path is None:
        user_layout = default_user_layout_path(resolved_config)
        if not user_layout.exists():
            user_layout.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(default_layout_path(), user_layout)
        selected_config = selected_config.with_overrides(layout_path=str(user_layout))
    save_config(selected_config, resolved_config)
    resolved_unit.parent.mkdir(parents=True, exist_ok=True)
    resolved_unit.write_text(
        render_user_unit(
            python_executable=python_executable,
            config_path=resolved_config,
            source_root=source_root,
        ),
        encoding="utf-8",
    )
    runner(["systemctl", "--user", "daemon-reload"], check=True)
    runner(["systemctl", "--user", "enable", "--now", SERVICE_NAME], check=True)
    return resolved_config, resolved_unit
