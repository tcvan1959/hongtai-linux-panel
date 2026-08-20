import os
import tempfile
import unittest
from pathlib import Path

from hongtai_panel.discovery import (
    SUPPORTED_USB_ID,
    discover_panels,
    read_usb_identity,
    resolve_panel_path,
)


class DiscoveryTests(unittest.TestCase):
    def test_discovers_stable_hongtai_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "ttyACM0"
            target.touch()
            link = root / "usb-HONGTAI_MONITOR-test"
            link.symlink_to(target)
            pattern = str(root / "*HONGTAI*")
            self.assertEqual(discover_panels([pattern]), [str(link)])
            self.assertEqual(resolve_panel_path(patterns=[pattern]), str(link))

    def test_falls_back_only_to_exact_supported_ttyacm_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            supported = root / "ttyACM0"
            unrelated = root / "ttyACM1"
            supported.touch()
            unrelated.touch()
            identities = {
                str(supported): SUPPORTED_USB_ID,
                str(unrelated): (0x1234, 0x5678),
            }
            self.assertEqual(
                discover_panels(
                    [],
                    fallback_pattern=str(root / "ttyACM*"),
                    identity_reader=identities.get,
                ),
                [str(supported)],
            )

    def test_stable_link_is_preferred_over_ttyacm_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stable = root / "usb-HONGTAI_MONITOR-test"
            fallback = root / "ttyACM0"
            stable.touch()
            fallback.touch()
            identity = lambda _path: SUPPORTED_USB_ID
            self.assertEqual(
                discover_panels(
                    [str(root / "*HONGTAI*")],
                    fallback_pattern=str(root / "ttyACM*"),
                    identity_reader=identity,
                ),
                [str(stable)],
            )

    def test_explicit_known_wrong_usb_identity_is_rejected(self) -> None:
        with tempfile.NamedTemporaryFile() as device:
            with self.assertRaisesRegex(RuntimeError, "refusing USB 1234:5678"):
                resolve_panel_path(
                    device.name,
                    identity_reader=lambda _path: (0x1234, 0x5678),
                )

    def test_reads_usb_identity_from_synthetic_sysfs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tty_class = root / "class" / "tty"
            usb_device = root / "devices" / "usb1" / "1-2"
            interface = usb_device / "1-2:1.0"
            interface.mkdir(parents=True)
            (usb_device / "idVendor").write_text("33c3\n", encoding="ascii")
            (usb_device / "idProduct").write_text("7802\n", encoding="ascii")
            (tty_class / "ttyACM0").mkdir(parents=True)
            (tty_class / "ttyACM0" / "device").symlink_to(interface)
            self.assertEqual(
                read_usb_identity("/dev/ttyACM0", tty_class=str(tty_class)),
                SUPPORTED_USB_ID,
            )

    def test_explicit_missing_device_is_rejected(self) -> None:
        with self.assertRaises(FileNotFoundError):
            resolve_panel_path("/definitely/not/a/device")

    def test_ambiguous_discovery_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "HONGTAI-one"
            second = root / "HONGTAI-two"
            first.touch()
            second.touch()
            with self.assertRaisesRegex(RuntimeError, "multiple"):
                resolve_panel_path(patterns=[str(root / "HONGTAI-*")])


if __name__ == "__main__":
    unittest.main()
