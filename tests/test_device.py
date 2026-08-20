import unittest
from unittest.mock import Mock, patch

from hongtai_panel.device import (
    DeviceInfo,
    HongtaiPanel,
    validate_brightness,
    validate_resolution,
)
from hongtai_panel.protocol import ProtocolError
from hongtai_panel.protocol import IMAGE_TERMINATOR, build_command, build_image_envelope


class DeviceBehaviorTests(unittest.TestCase):
    def test_brightness_uses_one_byte_payload(self) -> None:
        panel = HongtaiPanel("unused")
        panel._write_all = Mock()
        panel.set_brightness(80)
        panel._write_all.assert_called_once_with(build_command(0x03, b"\x50"))

    def test_brightness_rejects_invalid_values(self) -> None:
        panel = HongtaiPanel("unused")
        for value in (-1, 101):
            with self.assertRaises(ValueError):
                panel.set_brightness(value)
        with self.assertRaises(TypeError):
            panel.set_brightness(True)

    def test_brightness_validation_is_reusable_by_ui(self) -> None:
        self.assertEqual(validate_brightness(0), 0)
        self.assertEqual(validate_brightness(100), 100)
        with self.assertRaises(ValueError):
            validate_brightness(101)

    def test_resolution_validation_uses_device_report(self) -> None:
        def info(width, height):
            return DeviceInfo(None, None, None, None, width, height, None, None, None, {})

        self.assertEqual(validate_resolution(info(480, 320)), (480, 320))
        with self.assertRaisesRegex(ProtocolError, "did not report"):
            validate_resolution(info(None, None))
        with self.assertRaisesRegex(ProtocolError, "320x480"):
            validate_resolution(info(320, 480))

    def test_zero_second_hold_returns_without_refresh(self) -> None:
        panel = HongtaiPanel("unused")
        panel.refresh = Mock()
        panel.hold_display(0)
        panel.refresh.assert_not_called()

    def test_restart_is_exactly_one_command(self) -> None:
        panel = HongtaiPanel("unused")
        panel._write_all = Mock()
        panel.restart_panel()
        panel._write_all.assert_called_once_with(
            bytes.fromhex("55 aa 07 00 01 07 01")
        )

    def test_indefinite_hold_refreshes_until_interrupted(self) -> None:
        panel = HongtaiPanel("unused")
        panel.refresh = Mock(side_effect=KeyboardInterrupt)
        with patch("hongtai_panel.device.time.sleep") as sleep:
            with self.assertRaises(KeyboardInterrupt):
                panel.hold_display(None)
        sleep.assert_called_once_with(1.4)
        panel.refresh.assert_called_once_with()

    def test_hold_rejects_invalid_values(self) -> None:
        panel = HongtaiPanel("unused")
        with self.assertRaises(ValueError):
            panel.hold_display(-1)
        with self.assertRaises(ValueError):
            panel.hold_display(1, interval=0)

    def test_refresh_jpeg_and_commit_are_written_without_a_sleep_gap(self) -> None:
        panel = HongtaiPanel("unused")
        panel._write_all = Mock()
        jpeg = b"\xff\xd8test\xff\xd9"
        with patch("hongtai_panel.device.time.sleep") as sleep:
            panel.send_jpeg(jpeg, reset=False)
        sleep.assert_not_called()
        self.assertEqual(
            [call.args[0] for call in panel._write_all.call_args_list],
            [
                build_command(0x11),
                build_image_envelope(jpeg),
                IMAGE_TERMINATOR,
                build_command(0x11),
            ],
        )

    def test_post_upload_commit_can_be_disabled(self) -> None:
        panel = HongtaiPanel("unused")
        panel._write_all = Mock()
        jpeg = b"\xff\xd8test\xff\xd9"
        panel.send_jpeg(jpeg, reset=False, commit=False)
        self.assertEqual(len(panel._write_all.call_args_list), 3)

    def test_active_pipeline_can_upload_then_commit_without_leading_refresh(self) -> None:
        panel = HongtaiPanel("unused")
        panel._write_all = Mock()
        jpeg = b"\xff\xd8test\xff\xd9"
        panel.send_jpeg(jpeg, reset=False, wake=False)
        self.assertEqual(
            [call.args[0] for call in panel._write_all.call_args_list],
            [build_image_envelope(jpeg), IMAGE_TERMINATOR, build_command(0x11)],
        )


if __name__ == "__main__":
    unittest.main()
