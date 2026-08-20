"""Safe, explicit serial access to a Hongtai USB panel."""

from __future__ import annotations

import json
import array
import fcntl
import os
import select
import termios
import time
from dataclasses import dataclass
from typing import Any

from .protocol import (
    CMD_CLOSE,
    CMD_GET_DEVICE_INFO,
    CMD_REFRESH,
    CMD_RESTART,
    CMD_SET_BRIGHTNESS,
    IMAGE_TERMINATOR,
    MAGIC,
    PIPELINE_RESET,
    ProtocolError,
    build_command,
    build_image_envelope,
    frame_length_from_prefix,
    parse_command_frame,
)


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    status: int | None
    uid: str | None
    model: str | None
    version: str | None
    width: int | None
    height: int | None
    brightness: int | None
    angle: int | None
    region: str | None
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: bytes) -> "DeviceInfo":
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("device-information payload is not UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise ProtocolError("device-information response is not a JSON object")

        nested = decoded.get("data")
        if nested is not None and not isinstance(nested, dict):
            raise ProtocolError("device-information data field is not a JSON object")
        values = nested if isinstance(nested, dict) else decoded

        return cls(
            status=_optional_int(decoded.get("status")),
            uid=_optional_str(values.get("uid")),
            model=_optional_str(values.get("model")),
            version=_optional_str(values.get("version")),
            width=_optional_int(values.get("width")),
            height=_optional_int(values.get("height")),
            brightness=_optional_int(values.get("brightness")),
            angle=_optional_int(values.get("angle")),
            region=_optional_str(values.get("region")),
            raw=decoded,
        )


def validate_resolution(
    info: DeviceInfo, expected_width: int = 480, expected_height: int = 320
) -> tuple[int, int]:
    """Require the device-reported geometry expected by this bounded driver."""
    if info.width is None or info.height is None:
        raise ProtocolError("device information did not report width and height")
    actual = (info.width, info.height)
    expected = (expected_width, expected_height)
    if actual != expected:
        raise ProtocolError(
            f"device reports {actual[0]}x{actual[1]}; expected "
            f"{expected[0]}x{expected[1]}"
        )
    return actual


def validate_brightness(percent: int) -> int:
    """Validate and return the protocol's supported brightness percentage."""
    if isinstance(percent, bool) or not isinstance(percent, int):
        raise TypeError("brightness must be an integer")
    if not 0 <= percent <= 100:
        raise ValueError("brightness must be between 0 and 100")
    return percent


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


class HongtaiPanel:
    """A context-managed connection to one Hongtai serial panel."""

    def __init__(self, path: str = "/dev/ttyACM0") -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> "HongtaiPanel":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close_port()

    @property
    def is_open(self) -> bool:
        return self._fd is not None

    def open(self) -> None:
        if self._fd is not None:
            return
        if not hasattr(termios, "B2000000"):
            raise RuntimeError("this Python/OS does not expose 2,000,000 baud")

        flags = os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        fd = os.open(self.path, flags)
        try:
            if hasattr(termios, "TIOCEXCL"):
                fcntl.ioctl(fd, termios.TIOCEXCL)
            attrs = termios.tcgetattr(fd)
            attrs[0] = 0
            attrs[1] = 0
            attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attrs[3] = 0
            attrs[4] = termios.B2000000
            attrs[5] = termios.B2000000
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            termios.tcflush(fd, termios.TCIOFLUSH)
        except Exception:
            os.close(fd)
            raise
        self._fd = fd

    def close_port(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def reset_pipeline(self, settle_seconds: float = 0.2) -> None:
        self._write_all(PIPELINE_RESET)
        time.sleep(settle_seconds)

    def query_device_info(self, timeout: float = 3.0) -> DeviceInfo:
        self.reset_pipeline()
        self._write_all(build_command(CMD_GET_DEVICE_INFO))
        frame = self._read_frame(timeout)
        if frame.command != CMD_GET_DEVICE_INFO:
            raise ProtocolError(
                f"expected response command 0x06, received 0x{frame.command:02x}"
            )
        return DeviceInfo.from_payload(frame.payload)

    def refresh(self) -> None:
        self._write_all(build_command(CMD_REFRESH))

    def set_brightness(self, percent: int) -> None:
        """Set backlight brightness using the protocol's one-byte 0..100 value."""
        validate_brightness(percent)
        self._write_all(build_command(CMD_SET_BRIGHTNESS, bytes((percent,))))

    def restart_panel(self) -> None:
        """Request one board restart that causes USB re-enumeration.

        Verified firmware 3.2 restores its factory/default animation after the
        reboot. The current serial handle will become invalid. Callers must not
        retry, reconnect, or query the device automatically.
        """
        self._write_all(build_command(CMD_RESTART))

    def queued_input_bytes(self) -> int:
        """Return the kernel's unread-byte count without consuming input."""
        fd = self._require_fd()
        queued = array.array("i", [0])
        fcntl.ioctl(fd, termios.TIOCINQ, queued, True)
        return max(0, int(queued[0]))

    def read_available(self, *, timeout: float = 0.0, limit: int = 64 * 1024) -> bytes:
        """Read currently available panel input without waiting indefinitely."""
        if timeout < 0:
            raise ValueError("timeout cannot be negative")
        if limit <= 0:
            raise ValueError("limit must be positive")
        fd = self._require_fd()
        chunks: list[bytes] = []
        total = 0
        wait = timeout
        while total < limit:
            readable, _, _ = select.select([fd], [], [], wait)
            if not readable:
                break
            chunk = os.read(fd, min(4096, limit - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            wait = 0.0
        return b"".join(chunks)

    def hold_display(
        self, seconds: float | None = None, *, interval: float = 1.4
    ) -> None:
        """Keep the live pipeline active until timeout or interruption.

        ``seconds=None`` holds indefinitely. The verified firmware clears the
        frame shortly after these refresh commands stop.
        """
        if seconds is not None and seconds < 0:
            raise ValueError("seconds cannot be negative")
        if interval <= 0:
            raise ValueError("interval must be positive")

        deadline = None if seconds is None else time.monotonic() + seconds
        while deadline is None or time.monotonic() < deadline:
            delay = interval
            if deadline is not None:
                delay = min(delay, max(0, deadline - time.monotonic()))
            if delay <= 0:
                break
            time.sleep(delay)
            if deadline is None or time.monotonic() < deadline:
                self.refresh()

    def send_jpeg(
        self,
        jpeg: bytes,
        *,
        reset: bool = True,
        wake: bool = True,
        commit: bool = True,
    ) -> None:
        """Upload one JPEG and optionally refresh again to reveal it.

        Firmware 3.2 on the verified panel does not retain a newly uploaded
        frame until a following ``0x11`` command commits it to the display.
        """
        envelope = build_image_envelope(jpeg)
        if reset:
            self.reset_pipeline()
        if wake:
            self.refresh()
        self._write_all(envelope)
        self._write_all(IMAGE_TERMINATOR)
        if commit:
            self.refresh()

    def release_display(self) -> None:
        """Send firmware command 0x21; the verified panel may become blank."""
        self._write_all(build_command(CMD_CLOSE))

    def _require_fd(self) -> int:
        if self._fd is None:
            raise RuntimeError("panel serial port is not open")
        return self._fd

    def _write_all(self, data: bytes, timeout: float = 5.0) -> None:
        fd = self._require_fd()
        view = memoryview(data)
        deadline = time.monotonic() + timeout
        while view:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timed out writing to {self.path}")
            _, writable, _ = select.select([], [fd], [], remaining)
            if not writable:
                continue
            written = os.write(fd, view)
            view = view[written:]

    def _read_frame(self, timeout: float):
        fd = self._require_fd()
        data = bytearray()
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            readable, _, _ = select.select([fd], [], [], max(0, remaining))
            if not readable:
                break
            chunk = os.read(fd, 4096)
            if not chunk:
                continue
            data.extend(chunk)

            magic_at = data.find(MAGIC)
            if magic_at > 0:
                del data[:magic_at]
            if magic_at < 0 and len(data) > 1:
                del data[:-1]

            length = frame_length_from_prefix(data)
            if length is not None and len(data) >= length:
                return parse_command_frame(bytes(data[:length]))

        raise TimeoutError(f"no complete response received from {self.path}")
