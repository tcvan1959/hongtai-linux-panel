import threading
import unittest

from hongtai_panel.service import DynamicDisplayService, StaticDisplayService


class FakePanel:
    def __init__(self, path: str, stop_event: threading.Event) -> None:
        self.path = path
        self.stop_event = stop_event
        self.sent: list[bytes] = []
        self.refresh_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def send_jpeg(self, jpeg: bytes, **_options) -> None:
        self.sent.append(jpeg)

    def refresh(self) -> None:
        self.refresh_count += 1
        self.stop_event.set()


class ServiceTests(unittest.TestCase):
    def test_service_sends_and_refreshes_until_stopped(self) -> None:
        stop = threading.Event()
        created: list[FakePanel] = []

        def factory(path: str):
            panel = FakePanel(path, stop)
            created.append(panel)
            return panel

        service = StaticDisplayService(
            b"jpeg",
            refresh_interval=0.001,
            panel_factory=factory,
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        service.run(stop)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].path, "/dev/test-panel")
        self.assertEqual(created[0].sent, [b"jpeg"])
        self.assertEqual(created[0].refresh_count, 1)

    def test_service_reconnects_after_open_failure(self) -> None:
        stop = threading.Event()
        attempts = 0
        created: list[FakePanel] = []

        def factory(path: str):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("temporarily disconnected")
            panel = FakePanel(path, stop)
            created.append(panel)
            return panel

        service = StaticDisplayService(
            b"jpeg",
            refresh_interval=0.001,
            reconnect_delay=0,
            panel_factory=factory,
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        with self.assertLogs("hongtai_panel.service", level="WARNING") as captured:
            service.run(stop)
        self.assertEqual(attempts, 2)
        self.assertEqual(len(created), 1)
        self.assertIn("temporarily disconnected", captured.output[0])

    def test_dynamic_service_sends_changing_frame_without_second_reset(self) -> None:
        stop = threading.Event()
        sends: list[tuple[bool, bool, bool]] = []
        frames: list[bytes] = []

        class DynamicFakePanel(FakePanel):
            def send_jpeg(
                self,
                jpeg: bytes,
                *,
                reset: bool = True,
                wake: bool = True,
                commit: bool = True,
            ) -> None:
                frames.append(jpeg)
                sends.append((reset, wake, commit))
                if len(frames) == 2:
                    stop.set()

        frame_number = 0

        def provide_frame() -> bytes:
            nonlocal frame_number
            frame_number += 1
            return f"frame-{frame_number}".encode()

        service = DynamicDisplayService(
            provide_frame,
            frame_interval=0.001,
            panel_factory=lambda path: DynamicFakePanel(path, stop),
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        service.run(stop)
        self.assertEqual(frames, [b"frame-1", b"frame-2"])
        self.assertEqual(sends, [(True, True, True), (False, False, True)])

    def test_dynamic_service_refreshes_between_slower_full_frames(self) -> None:
        stop = threading.Event()
        created: list[FakePanel] = []

        def factory(path: str):
            panel = FakePanel(path, stop)
            created.append(panel)
            return panel

        service = DynamicDisplayService(
            lambda: b"frame",
            frame_interval=1.0,
            refresh_interval=0.001,
            panel_factory=factory,
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        service.run(stop)
        self.assertEqual(created[0].sent, [b"frame"])
        self.assertEqual(created[0].refresh_count, 1)

    def test_no_reconnect_mode_stops_after_first_failure(self) -> None:
        stop = threading.Event()
        attempts = 0

        def factory(_path: str):
            nonlocal attempts
            attempts += 1
            raise OSError("stop here")

        service = DynamicDisplayService(
            lambda: b"frame",
            reconnect=False,
            panel_factory=factory,
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        with self.assertLogs("hongtai_panel.service", level="WARNING"):
            service.run(stop)
        self.assertTrue(stop.is_set())
        self.assertEqual(attempts, 1)
        self.assertIsInstance(service.last_error, OSError)

    def test_dynamic_service_reports_operations(self) -> None:
        stop = threading.Event()
        observed: list[tuple[str, int | None]] = []

        class ObservedPanel(FakePanel):
            def send_jpeg(self, jpeg: bytes, **_options) -> None:
                self.sent.append(jpeg)

            def refresh(self) -> None:
                self.refresh_count += 1
                stop.set()

        service = DynamicDisplayService(
            lambda: b"jpeg",
            frame_interval=1.0,
            refresh_interval=0.001,
            operation_observer=lambda label, _duration, size: observed.append(
                (label, size)
            ),
            panel_factory=lambda path: ObservedPanel(path, stop),
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        service.run(stop)
        self.assertEqual(observed, [("first_frame", 4), ("refresh", None)])

    def test_health_check_failure_stops_without_reconnect(self) -> None:
        stop = threading.Event()

        class UnusedPanel(FakePanel):
            def send_jpeg(self, jpeg: bytes, **_options) -> None:
                self.fail("send_jpeg should not be reached")

        service = DynamicDisplayService(
            lambda: b"jpeg",
            reconnect=False,
            health_check=lambda: (_ for _ in ()).throw(
                RuntimeError("kernel event")
            ),
            panel_factory=lambda path: UnusedPanel(path, stop),
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        with self.assertLogs("hongtai_panel.service", level="WARNING"):
            service.run(stop)
        self.assertTrue(stop.is_set())
        self.assertRegex(str(service.last_error), "kernel event")


if __name__ == "__main__":
    unittest.main()
