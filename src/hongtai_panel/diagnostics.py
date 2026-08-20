"""Passive serial-response capture for bounded physical diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import statistics
import subprocess
import time
from collections.abc import Callable
from typing import Protocol

from .protocol import MAGIC, CommandFrame, ProtocolError, frame_length_from_prefix, parse_command_frame


class InputPanel(Protocol):
    def queued_input_bytes(self) -> int: ...
    def read_available(self, *, timeout: float = 0.0, limit: int = 64 * 1024) -> bytes: ...


@dataclass(frozen=True, slots=True)
class ReplyEvent:
    label: str
    queued_before: int
    queued_after: int
    byte_count: int
    frames: tuple[CommandFrame, ...]


@dataclass(slots=True)
class ReplyCapture:
    """Collect bounded evidence without assuming that replies are present."""

    max_sample_bytes: int = 256
    total_bytes: int = 0
    high_water_bytes: int = 0
    malformed_bytes: int = 0
    frame_count: int = 0
    events: list[ReplyEvent] = field(default_factory=list)
    sample: bytearray = field(default_factory=bytearray)
    _buffer: bytearray = field(default_factory=bytearray, repr=False)

    def poll(
        self,
        panel: InputPanel,
        label: str,
        *,
        timeout: float = 0.05,
    ) -> ReplyEvent:
        queued_before = panel.queued_input_bytes()
        self.high_water_bytes = max(self.high_water_bytes, queued_before)
        data = panel.read_available(timeout=timeout)
        queued_after = panel.queued_input_bytes()
        self.high_water_bytes = max(self.high_water_bytes, queued_after)
        self.total_bytes += len(data)
        if len(self.sample) < self.max_sample_bytes:
            remaining = self.max_sample_bytes - len(self.sample)
            self.sample.extend(data[:remaining])
        frames = tuple(self._feed(data))
        event = ReplyEvent(
            label=label,
            queued_before=queued_before,
            queued_after=queued_after,
            byte_count=len(data),
            frames=frames,
        )
        self.events.append(event)
        return event

    def _feed(self, data: bytes) -> list[CommandFrame]:
        self._buffer.extend(data)
        frames: list[CommandFrame] = []
        while self._buffer:
            magic_at = self._buffer.find(MAGIC)
            if magic_at < 0:
                keep = 1 if self._buffer[-1:] == MAGIC[:1] else 0
                discarded = len(self._buffer) - keep
                self.malformed_bytes += discarded
                if keep:
                    self._buffer[:] = self._buffer[-1:]
                else:
                    self._buffer.clear()
                break
            if magic_at:
                self.malformed_bytes += magic_at
                del self._buffer[:magic_at]
            try:
                length = frame_length_from_prefix(self._buffer)
            except ProtocolError:
                self.malformed_bytes += 1
                del self._buffer[0]
                continue
            if length is None or len(self._buffer) < length:
                break
            raw = bytes(self._buffer[:length])
            del self._buffer[:length]
            try:
                frames.append(parse_command_frame(raw))
            except ProtocolError:
                self.malformed_bytes += len(raw)
        self.frame_count += len(frames)
        return frames

    def finish(self) -> None:
        self.malformed_bytes += len(self._buffer)
        self._buffer.clear()

    def summary(self) -> dict[str, object]:
        labels: dict[str, dict[str, int]] = {}
        frame_samples: list[dict[str, object]] = []
        for event in self.events:
            label = labels.setdefault(
                event.label,
                {"polls": 0, "bytes": 0, "frames": 0, "high_water_bytes": 0},
            )
            label["polls"] += 1
            label["bytes"] += event.byte_count
            label["frames"] += len(event.frames)
            label["high_water_bytes"] = max(
                label["high_water_bytes"],
                event.queued_before,
                event.queued_after,
            )
            for frame in event.frames:
                if len(frame_samples) >= 16:
                    break
                frame_samples.append(
                    {
                        "label": event.label,
                        "command": f"0x{frame.command:02x}",
                        "payload_hex": frame.payload.hex(" "),
                        "raw_hex": frame.raw.hex(" "),
                    }
                )
        return {
            "polls": len(self.events),
            "total_bytes": self.total_bytes,
            "high_water_bytes": self.high_water_bytes,
            "frame_count": self.frame_count,
            "malformed_bytes": self.malformed_bytes,
            "sample_hex": bytes(self.sample).hex(" "),
            "by_operation": labels,
            "frame_samples": frame_samples,
        }


@dataclass(frozen=True, slots=True)
class WriteEvent:
    byte_count: int
    duration_seconds: float
    error: str | None = None


@dataclass(slots=True)
class WriteCapture:
    """Record low-overhead timings for one bounded diagnostic session."""

    events: list[WriteEvent] = field(default_factory=list)

    def record(
        self,
        byte_count: int,
        duration_seconds: float,
        error: BaseException | None = None,
    ) -> None:
        self.events.append(
            WriteEvent(
                byte_count=byte_count,
                duration_seconds=duration_seconds,
                error=None if error is None else f"{type(error).__name__}: {error}",
            )
        )

    def summary(self) -> dict[str, object]:
        durations = [event.duration_seconds for event in self.events]
        successful = [
            event.duration_seconds for event in self.events if event.error is None
        ]
        ordered = sorted(successful)

        def percentile(fraction: float) -> float | None:
            if not ordered:
                return None
            index = min(len(ordered) - 1, round((len(ordered) - 1) * fraction))
            return ordered[index]

        return {
            "write_count": len(self.events),
            "successful_write_count": len(successful),
            "error_count": len(self.events) - len(successful),
            "total_bytes": sum(event.byte_count for event in self.events),
            "min_seconds": min(successful) if successful else None,
            "median_seconds": statistics.median(successful) if successful else None,
            "p95_seconds": percentile(0.95),
            "max_seconds": max(durations) if durations else None,
            "errors": [event.error for event in self.events if event.error is not None],
        }


@dataclass(slots=True)
class HostHealthCheck:
    """Fail a bounded run on tty loss or a new panel-related kernel event."""

    device_path: str
    kernel_usb_path: str
    check_interval: float = 0.5
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
    _kernel_since: float = field(default_factory=time.time, init=False, repr=False)
    _last_kernel_check: float = field(default=float("-inf"), init=False, repr=False)

    def __call__(self) -> None:
        path = Path(self.device_path)
        if not path.exists():
            raise RuntimeError(f"panel tty disappeared: {self.device_path}")
        tty_name = path.resolve().name
        now = time.monotonic()
        if now - self._last_kernel_check < self.check_interval:
            return
        self._last_kernel_check = now
        result = self.runner(
            [
                "journalctl",
                "-k",
                "--no-pager",
                "-o",
                "cat",
                "--since",
                f"@{self._kernel_since:.6f}",
            ],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit status {result.returncode}"
            raise RuntimeError(f"kernel health check failed: {detail}")
        usb_marker = f"usb {self.kernel_usb_path}".lower()
        for line in result.stdout.splitlines():
            lowered = line.lower()
            if usb_marker in lowered or "cdc_acm" in lowered and tty_name.lower() in lowered:
                raise RuntimeError(f"new panel-related kernel event: {line.strip()}")
