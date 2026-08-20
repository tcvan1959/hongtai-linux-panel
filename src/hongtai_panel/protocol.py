"""Pure functions for the Hongtai command and live-image protocol."""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = b"\x55\xaa"
PIPELINE_RESET = b"\xff\xd9\xff\xd9\x00\x00\x00\x00"
IMAGE_TERMINATOR = b"\xff\xd9\xff\xd9"
MAX_JPEG_BYTES = 80 * 1024

CMD_RESTART = 0x01
CMD_SET_BRIGHTNESS = 0x03
CMD_GET_DEVICE_INFO = 0x06
CMD_REFRESH = 0x11
CMD_CLOSE = 0x21


class ProtocolError(ValueError):
    """Raised when a protocol frame is malformed or fails validation."""


@dataclass(frozen=True, slots=True)
class CommandFrame:
    command: int
    payload: bytes
    raw: bytes


def checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def build_command(command: int, payload: bytes = b"") -> bytes:
    if not 0 <= command <= 0xFF:
        raise ValueError("command must fit in one byte")
    if len(payload) > 0xFFFF - 7:
        raise ValueError("payload is too large for a command frame")

    frame = bytearray(MAGIC)
    frame.extend(struct.pack("<H", len(payload) + 7))
    frame.append(command)
    frame.extend(payload)
    frame.extend(struct.pack("<H", checksum(frame)))
    return bytes(frame)


def parse_command_frame(data: bytes) -> CommandFrame:
    if len(data) < 7:
        raise ProtocolError("command frame is shorter than seven bytes")
    if data[:2] != MAGIC:
        raise ProtocolError("command frame has invalid magic bytes")

    declared_length = struct.unpack_from("<H", data, 2)[0]
    if declared_length != len(data):
        raise ProtocolError(
            f"command frame length is {len(data)}, expected {declared_length}"
        )

    expected = struct.unpack_from("<H", data, len(data) - 2)[0]
    actual = checksum(data[:-2])
    if expected != actual:
        raise ProtocolError(
            f"command checksum is 0x{expected:04x}, expected 0x{actual:04x}"
        )

    return CommandFrame(command=data[4], payload=data[5:-2], raw=data)


def frame_length_from_prefix(data: bytes) -> int | None:
    """Return a complete frame length when a plausible prefix is available."""
    if len(data) < 4 or data[:2] != MAGIC:
        return None
    length = struct.unpack_from("<H", data, 2)[0]
    if length < 7:
        raise ProtocolError(f"invalid declared command length: {length}")
    return length


def build_image_envelope(jpeg: bytes, max_bytes: int = MAX_JPEG_BYTES) -> bytes:
    if not jpeg.startswith(b"\xff\xd8") or not jpeg.endswith(b"\xff\xd9"):
        raise ProtocolError("image data is not a complete JPEG")
    if len(jpeg) > max_bytes:
        raise ProtocolError(
            f"JPEG is {len(jpeg)} bytes; device limit is {max_bytes} bytes"
        )

    body = struct.pack("<I", len(jpeg)) + jpeg
    return body + struct.pack("<H", checksum(body))
