import struct
import unittest

from hongtai_panel.protocol import (
    CMD_GET_DEVICE_INFO,
    CMD_RESTART,
    MAX_JPEG_BYTES,
    ProtocolError,
    build_command,
    build_image_envelope,
    checksum,
    frame_length_from_prefix,
    parse_command_frame,
)


class ProtocolTests(unittest.TestCase):
    def test_build_known_refresh_command(self) -> None:
        self.assertEqual(
            build_command(0x11), bytes.fromhex("55 aa 07 00 11 17 01")
        )

    def test_build_known_restart_command(self) -> None:
        self.assertEqual(
            build_command(CMD_RESTART), bytes.fromhex("55 aa 07 00 01 07 01")
        )

    def test_command_round_trip(self) -> None:
        raw = build_command(CMD_GET_DEVICE_INFO, b"hello")
        parsed = parse_command_frame(raw)
        self.assertEqual(parsed.command, CMD_GET_DEVICE_INFO)
        self.assertEqual(parsed.payload, b"hello")
        self.assertEqual(parsed.raw, raw)

    def test_parse_rejects_bad_magic(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "magic"):
            parse_command_frame(bytes.fromhex("00 aa 07 00 06 0d 01"))

    def test_parse_rejects_bad_length(self) -> None:
        raw = bytearray(build_command(0x06))
        raw[2] = 8
        with self.assertRaisesRegex(ProtocolError, "length"):
            parse_command_frame(bytes(raw))

    def test_parse_rejects_bad_checksum(self) -> None:
        raw = bytearray(build_command(0x06))
        raw[-1] ^= 0x01
        with self.assertRaisesRegex(ProtocolError, "checksum"):
            parse_command_frame(bytes(raw))

    def test_frame_length_requires_complete_prefix(self) -> None:
        self.assertIsNone(frame_length_from_prefix(b""))
        self.assertIsNone(frame_length_from_prefix(b"\x55\xaa\x07"))
        self.assertEqual(frame_length_from_prefix(build_command(0x06)[:4]), 7)

    def test_image_envelope_layout_and_checksum(self) -> None:
        jpeg = b"\xff\xd8payload\xff\xd9"
        envelope = build_image_envelope(jpeg)
        self.assertEqual(struct.unpack_from("<I", envelope)[0], len(jpeg))
        self.assertEqual(envelope[4:-2], jpeg)
        self.assertEqual(
            struct.unpack_from("<H", envelope, len(envelope) - 2)[0],
            checksum(envelope[:-2]),
        )

    def test_image_envelope_rejects_non_jpeg(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "JPEG"):
            build_image_envelope(b"not an image")

    def test_image_envelope_enforces_limit(self) -> None:
        oversized = b"\xff\xd8" + (b"x" * MAX_JPEG_BYTES) + b"\xff\xd9"
        with self.assertRaisesRegex(ProtocolError, "limit"):
            build_image_envelope(oversized)


if __name__ == "__main__":
    unittest.main()
