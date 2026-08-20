import threading
import time
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

from hongtai_panel.control_app import PanelController
from hongtai_panel.device import DeviceInfo


def supported_info(width=480, height=320):
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
    def __init__(self, path, info, instances, restart_error=None):
        self.path = path
        self.info = info
        self.restart_error = restart_error
        self.sent = []
        self.refreshes = 0
        self.brightness = []
        self.queries = 0
        self.restarts = 0
        self.closed = False
        instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def query_device_info(self):
        self.queries += 1
        return self.info

    def send_jpeg(self, jpeg, **options):
        self.sent.append((jpeg, options))

    def refresh(self):
        self.refreshes += 1

    def set_brightness(self, percent):
        self.brightness.append(percent)

    def restart_panel(self):
        self.restarts += 1
        if self.restart_error is not None:
            raise self.restart_error


def wait_for(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.002)
    raise AssertionError("condition was not reached")


class PanelControllerTests(unittest.TestCase):
    def make_controller(
        self,
        info=None,
        restart_error=None,
        *,
        media_dir=None,
        use_real_frames=False,
    ):
        instances = []
        selected_info = info or supported_info()

        def factory(path):
            return FakePanel(path, selected_info, instances, restart_error)

        controller = PanelController(
            panel_factory=factory,
            path_resolver=lambda _explicit: "/dev/test-panel",
            frame_factory=(
                None
                if use_real_frames
                else lambda layout, _info: f"jpeg-{layout}".encode()
            ),
            media_dir=media_dir,
            frame_interval=0.02,
            refresh_interval=0.005,
        )
        return controller, instances

    @staticmethod
    def png_bytes(size=(80, 80), color="#0ea5e9"):
        output = BytesIO()
        Image.new("RGB", size, color).save(output, "PNG")
        return output.getvalue()

    def test_detect_reports_verified_identity_and_closes_probe(self):
        controller, instances = self.make_controller()
        state = controller.detect()
        self.assertEqual(state["state"], "detected")
        self.assertEqual(state["path"], "/dev/test-panel")
        self.assertEqual(state["model"], "TXW818-ST7796-3.5inch-hor")
        self.assertEqual((state["width"], state["height"]), (480, 320))
        self.assertTrue(instances[0].closed)

    def test_start_brightness_stop_lifecycle_closes_stream(self):
        controller, instances = self.make_controller()
        controller.detect()
        state = controller.start("dashboard", 70)
        self.assertIn(state["state"], {"starting", "streaming"})
        wait_for(lambda: controller.snapshot()["state"] == "streaming")
        stream_panel = instances[-1]
        wait_for(lambda: stream_panel.sent)
        self.assertEqual(stream_panel.sent[0][0], b"jpeg-dashboard")
        self.assertEqual(stream_panel.brightness, [70])

        state = controller.set_brightness(45)
        self.assertEqual(state["brightness"], 45)
        wait_for(lambda: stream_panel.brightness == [70, 45])

        state = controller.stop()
        self.assertEqual(state["state"], "stopped")
        self.assertTrue(stream_panel.closed)
        self.assertFalse(
            any(
                thread.name == "hongtai-panel-stream" and thread.is_alive()
                for thread in threading.enumerate()
            )
        )

    def test_brightness_when_stopped_uses_bounded_connection(self):
        controller, instances = self.make_controller()
        controller.detect()
        state = controller.set_brightness(60)
        self.assertEqual(state["brightness"], 60)
        self.assertEqual(instances[-1].brightness, [60])
        self.assertTrue(instances[-1].closed)

    def test_restore_default_requires_a_fully_stopped_stream(self):
        controller, instances = self.make_controller()
        detected = controller.detect()
        self.assertFalse(detected["can_restore_default"])
        with self.assertRaisesRegex(RuntimeError, "fully stopped"):
            controller.restore_default_display()

        controller.start("orientation", 80)
        wait_for(lambda: controller.snapshot()["state"] == "streaming")
        with self.assertRaisesRegex(RuntimeError, "stop the live display"):
            controller.restore_default_display()
        self.assertFalse(controller.snapshot()["can_restore_default"])
        self.assertEqual(sum(panel.restarts for panel in instances), 0)
        controller.stop()
        self.assertTrue(controller.snapshot()["can_restore_default"])

    def test_restore_default_is_one_shot_and_does_not_redetect(self):
        controller, instances = self.make_controller()
        controller.detect()
        controller.start("orientation", 80)
        wait_for(lambda: controller.snapshot()["state"] == "streaming")
        controller.stop()

        state = controller.restore_default_display()

        self.assertEqual(state["state"], "restarting")
        self.assertIsNone(state["path"])
        self.assertFalse(state["can_restore_default"])
        self.assertEqual(len(instances), 3)
        self.assertEqual(instances[-1].restarts, 1)
        self.assertEqual(instances[-1].queries, 0)
        self.assertTrue(instances[-1].closed)
        self.assertEqual(sum(panel.restarts for panel in instances), 1)

    def test_restore_default_write_failure_is_visible_and_not_retried(self):
        controller, instances = self.make_controller(
            restart_error=TimeoutError("restart write timed out")
        )
        controller.detect()
        controller.start("orientation", 80)
        wait_for(lambda: controller.snapshot()["state"] == "streaming")
        controller.stop()

        with self.assertRaisesRegex(TimeoutError, "restart write timed out"):
            controller.restore_default_display()

        state = controller.snapshot()
        self.assertEqual(state["state"], "error")
        self.assertEqual(state["error"], "restart write timed out")
        self.assertEqual(sum(panel.restarts for panel in instances), 1)
        self.assertEqual(instances[-1].queries, 0)
        self.assertTrue(instances[-1].closed)

    def test_invalid_layout_and_brightness_are_rejected_before_start(self):
        controller, instances = self.make_controller()
        with self.assertRaisesRegex(ValueError, "unknown built-in layout"):
            controller.start("unknown")
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            controller.start("orientation", 101)
        self.assertEqual(instances, [])

    def test_missing_device_sets_visible_error_state(self):
        controller = PanelController(
            path_resolver=lambda _explicit: (_ for _ in ()).throw(
                FileNotFoundError("no serial path")
            )
        )
        with self.assertRaisesRegex(FileNotFoundError, "no serial path"):
            controller.detect()
        state = controller.snapshot()
        self.assertEqual(state["state"], "error")
        self.assertEqual(state["error"], "no serial path")

    def test_unsupported_resolution_sets_error_without_streaming(self):
        controller, instances = self.make_controller(supported_info(320, 480))
        with self.assertRaisesRegex(ValueError, "320x480"):
            controller.detect()
        self.assertEqual(controller.snapshot()["state"], "error")
        self.assertTrue(instances[0].closed)

    def test_image_selection_previews_without_starting_stream(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, instances = self.make_controller(
                media_dir=directory,
                use_real_frames=True,
            )
            state = controller.select_uploaded_image("private.png", self.png_bytes())
            self.assertEqual(state["selected_image"], "private.png")
            self.assertEqual(state["selected_image_source"], "chosen file")
            self.assertEqual(state["state"], "disconnected")
            self.assertEqual(instances, [])
            with Image.open(BytesIO(controller.preview("image"))) as preview:
                self.assertEqual(preview.size, (480, 320))

    def test_private_library_selection_and_display_use_existing_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory)
            (media / "library.jpg").write_bytes(self.png_bytes())
            controller, instances = self.make_controller(
                media_dir=media,
                use_real_frames=True,
            )
            library = controller.media_library()
            self.assertEqual(library["files"], ["library.jpg"])
            selected = controller.select_library_image("library.jpg")
            self.assertEqual(selected["layout"], "image")
            self.assertFalse(selected["can_display_image"])
            controller.detect()
            self.assertTrue(controller.snapshot()["can_display_image"])
            expected = controller.preview("image")
            controller.start("image", 80)
            wait_for(lambda: controller.snapshot()["state"] == "streaming")
            stream_panel = instances[-1]
            wait_for(lambda: stream_panel.sent)
            self.assertEqual(stream_panel.sent[0][0], expected)
            with self.assertRaisesRegex(RuntimeError, "stop the live display"):
                controller.select_uploaded_image("other.png", self.png_bytes())
            stopped = controller.stop()
            self.assertEqual(stopped["state"], "stopped")
            self.assertEqual(stopped["selected_image"], "library.jpg")

    def test_image_display_requires_a_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            controller, instances = self.make_controller(media_dir=directory)
            with self.assertRaisesRegex(RuntimeError, "choose a PNG or JPEG"):
                controller.start("image")
            self.assertEqual(instances, [])


if __name__ == "__main__":
    unittest.main()
