"""Dependency-light Linux system telemetry for dashboard rendering."""

from __future__ import annotations

import csv
import glob
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class SystemMetrics:
    captured_at: datetime
    cpu_percent: float | None
    cpu_temp_c: float | None
    memory_percent: float | None
    memory_used_bytes: int | None
    memory_total_bytes: int | None
    gpu_name: str | None
    gpu_percent: float | None
    gpu_temp_c: float | None
    gpu_memory_used_bytes: int | None
    gpu_memory_total_bytes: int | None


def read_cpu_times(path: str = "/proc/stat") -> tuple[int, int]:
    fields = Path(path).read_text(encoding="utf-8").splitlines()[0].split()
    if not fields or fields[0] != "cpu" or len(fields) < 5:
        raise ValueError(f"invalid aggregate CPU line in {path}")
    values = [int(value) for value in fields[1:]]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return idle, sum(values)


def calculate_cpu_percent(
    previous: tuple[int, int] | None, current: tuple[int, int]
) -> float | None:
    if previous is None:
        return None
    idle_delta = current[0] - previous[0]
    total_delta = current[1] - previous[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0))


def read_memory(path: str = "/proc/meminfo") -> tuple[int, int, float]:
    values: dict[str, int] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, raw = line.split(":", 1)
        number = raw.strip().split()[0]
        values[key] = int(number) * 1024
    total = values["MemTotal"]
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(0, total - available)
    percent = used / total * 100.0 if total else 0.0
    return used, total, percent


def read_hwmon_temperature(
    chip_name: str,
    *,
    preferred_labels: tuple[str, ...] = (),
    hwmon_pattern: str = "/sys/class/hwmon/hwmon*",
) -> float | None:
    candidates: list[tuple[int, float]] = []
    for chip_path in glob.glob(hwmon_pattern):
        chip = Path(chip_path)
        try:
            if (chip / "name").read_text().strip() != chip_name:
                continue
        except OSError:
            continue
        for input_path_text in glob.glob(str(chip / "temp*_input")):
            input_path = Path(input_path_text)
            label_path = input_path.with_name(input_path.name.replace("_input", "_label"))
            try:
                value = float(input_path.read_text().strip()) / 1000.0
                label = label_path.read_text().strip() if label_path.exists() else ""
            except (OSError, ValueError):
                continue
            rank = preferred_labels.index(label) if label in preferred_labels else len(preferred_labels)
            candidates.append((rank, value))
    return min(candidates, default=(0, None), key=lambda item: item[0])[1]


def read_amd_gpu(
    drm_pattern: str = "/sys/class/drm/card[0-9]*",
    hwmon_pattern: str = "/sys/class/hwmon/hwmon*",
) -> tuple[str, float | None, float | None, int | None, int | None] | None:
    for card_path_text in sorted(glob.glob(drm_pattern)):
        device = Path(card_path_text) / "device"
        try:
            if (device / "vendor").read_text().strip().lower() != "0x1002":
                continue
        except OSError:
            continue

        def optional_int(name: str) -> int | None:
            try:
                return int((device / name).read_text().strip())
            except (OSError, ValueError):
                return None

        return (
            "AMD GPU",
            _optional_float(optional_int("gpu_busy_percent")),
            read_hwmon_temperature(
                "amdgpu", preferred_labels=("edge",), hwmon_pattern=hwmon_pattern
            ),
            optional_int("mem_info_vram_used"),
            optional_int("mem_info_vram_total"),
        )
    return None


def _optional_float(value: int | None) -> float | None:
    return None if value is None else float(value)


def read_nvidia_gpu(
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, float | None, float | None, int | None, int | None] | None:
    command = [
        "nvidia-smi",
        "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        result = runner(command, capture_output=True, text=True, timeout=1, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        row = next(csv.reader([result.stdout.splitlines()[0]], skipinitialspace=True))
        name, temp, usage, memory_used, memory_total = [value.strip() for value in row]
        return (
            name,
            float(usage),
            float(temp),
            int(float(memory_used) * 1024 * 1024),
            int(float(memory_total) * 1024 * 1024),
        )
    except (ValueError, StopIteration):
        return None


class SystemMetricsCollector:
    def __init__(
        self,
        *,
        proc_stat: str = "/proc/stat",
        meminfo: str = "/proc/meminfo",
        hwmon_pattern: str = "/sys/class/hwmon/hwmon*",
        drm_pattern: str = "/sys/class/drm/card[0-9]*",
        nvidia_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.proc_stat = proc_stat
        self.meminfo = meminfo
        self.hwmon_pattern = hwmon_pattern
        self.drm_pattern = drm_pattern
        self.nvidia_runner = nvidia_runner
        self._previous_cpu: tuple[int, int] | None = None

    def collect(self) -> SystemMetrics:
        current_cpu = read_cpu_times(self.proc_stat)
        cpu_percent = calculate_cpu_percent(self._previous_cpu, current_cpu)
        self._previous_cpu = current_cpu
        used, total, memory_percent = read_memory(self.meminfo)
        cpu_temp = read_hwmon_temperature(
            "k10temp",
            preferred_labels=("Tctl", "Tdie", "Package id 0"),
            hwmon_pattern=self.hwmon_pattern,
        )

        gpu = read_nvidia_gpu(self.nvidia_runner)
        if gpu is None:
            gpu = read_amd_gpu(self.drm_pattern, self.hwmon_pattern)
        gpu_name, gpu_percent, gpu_temp, gpu_used, gpu_total = (
            gpu if gpu is not None else (None, None, None, None, None)
        )

        return SystemMetrics(
            captured_at=datetime.now(),
            cpu_percent=cpu_percent,
            cpu_temp_c=cpu_temp,
            memory_percent=memory_percent,
            memory_used_bytes=used,
            memory_total_bytes=total,
            gpu_name=gpu_name,
            gpu_percent=gpu_percent,
            gpu_temp_c=gpu_temp,
            gpu_memory_used_bytes=gpu_used,
            gpu_memory_total_bytes=gpu_total,
        )
