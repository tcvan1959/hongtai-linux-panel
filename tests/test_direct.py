import threading
import unittest

from hongtai_panel.device import DeviceInfo
from hongtai_panel.direct import stream_demo


def device_info(width=480, height=320):
    return DeviceInfo(
        None,
        "test-uid",
        "TXW818-ST7796-3.5inch-hor",
        "3.2",
        width,
        height,
        80,
        0,
        None,
        {},
    )


class FakePanel:
    def __init__(self, stop_event: threading.Event | None = None) -> None:
        self.stop_event = stop_event
        self.sends = []
        self.refreshes = 0
        self.brightness = []

    def send_jpeg(self, jpeg, **options):
        self.sends.append((jpeg, options))
        if self.stop_event is not None and len(self.sends) == 2:
            self.stop_event.set()

    def refresh(self):
        self.refreshes += 1

    def set_brightness(self, percent):
        self.brightness.append(percent)


class DirectDriverTests(unittest.TestCase):
    def test_bounded_zero_hardware_session_stops_and_sets_brightness(self) -> None:
        panel = FakePanel()
        frames = stream_demo(
            panel,
            device_info(),
            lambda: b"jpeg",
            threading.Event(),
            duration=0.002,
            frame_interval=1,
            refresh_interval=0.001,
            brightness=75,
        )
        self.assertEqual(frames, 1)
        self.assertEqual(panel.brightness, [75])
        self.assertGreaterEqual(panel.refreshes, 1)

    def test_stop_event_ends_continuous_stream(self) -> None:
        stop = threading.Event()
        panel = FakePanel(stop)
        number = 0

        def frame():
            nonlocal number
            number += 1
            return f"jpeg-{number}".encode()

        frames = stream_demo(
            panel,
            device_info(),
            frame,
            stop,
            frame_interval=0.001,
            refresh_interval=0.001,
        )
        self.assertEqual(frames, 2)
        self.assertEqual(panel.sends[0][1], {})
        self.assertEqual(
            panel.sends[1][1],
            {"reset": False, "wake": False, "commit": True},
        )

    def test_resolution_is_checked_before_any_write(self) -> None:
        panel = FakePanel()
        with self.assertRaisesRegex(ValueError, "320x480"):
            stream_demo(
                panel,
                device_info(320, 480),
                lambda: b"jpeg",
                threading.Event(),
                duration=0.001,
            )
        self.assertEqual(panel.sends, [])


if __name__ == "__main__":
    unittest.main()
