import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from hongtai_panel.editor import create_editor_server


class FakeController:
    def __init__(self):
        self.state = "disconnected"
        self.closed = False
        self.restore_calls = 0
        self.selected_image = None
        self.selected_image_source = None
        self.media_select_calls = 0
        self.media_upload_calls = 0

    def snapshot(self):
        return {
            "state": self.state,
            "path": None,
            "model": None,
            "firmware": None,
            "width": None,
            "height": None,
            "brightness": 80,
            "layout": "orientation",
            "layout_name": "Orientation test",
            "layouts": {
                "orientation": "Orientation test",
                "image": "Selected image",
            },
            "selected_image": self.selected_image,
            "selected_image_source": self.selected_image_source,
            "can_display_image": bool(self.selected_image),
            "error": None,
            "can_restore_default": self.state == "stopped",
        }

    def detect(self):
        self.state = "detected"
        return self.snapshot()

    def start(self, layout, brightness):
        self.state = "streaming"
        return self.snapshot()

    def stop(self):
        self.state = "stopped"
        return self.snapshot()

    def set_brightness(self, _brightness):
        return self.snapshot()

    def restore_default_display(self):
        self.restore_calls += 1
        self.state = "restarting"
        return self.snapshot()

    def preview(self, _layout):
        return b"jpeg-preview"

    def media_library(self):
        return {
            "directory": "display_media/local",
            "files": ["library.png"],
            "selected_image": self.selected_image,
            "selected_image_source": self.selected_image_source,
        }

    def select_library_image(self, name):
        self.media_select_calls += 1
        self.selected_image = name
        self.selected_image_source = "private library"
        return self.snapshot()

    def select_uploaded_image(self, name, data):
        self.media_upload_calls += 1
        self.selected_image = name
        self.selected_image_source = "chosen file"
        self.uploaded_data = data
        return self.snapshot()

    def close(self):
        self.closed = True


def sample_layout():
    return {
        "version": 1,
        "name": "Control HTTP test",
        "width": 480,
        "height": 320,
        "background": "#080d18",
        "widgets": [],
    }


class ControlHttpTests(unittest.TestCase):
    def test_control_surface_status_preview_and_authorized_action(self):
        with tempfile.TemporaryDirectory() as directory:
            layout = Path(directory) / "layout.json"
            layout.write_text(json.dumps(sample_layout()), encoding="utf-8")
            controller = FakeController()
            server = create_editor_server(
                layout, port=0, controller=controller, control_mode=True
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(server.url, timeout=2) as response:
                    control_html = response.read()
                self.assertIn(b"Panel Control", control_html)
                self.assertIn(
                    b"Restore default display (restarts panel)", control_html
                )
                self.assertIn(b"Browse / Choose image", control_html)
                with urllib.request.urlopen(
                    server.url + "control.js", timeout=2
                ) as response:
                    control_js = response.read()
                self.assertIn(b"Display image", control_js)
                self.assertIn(b"window.confirm", control_js)
                self.assertIn(b"/api/panel/restore-default", control_js)
                with urllib.request.urlopen(
                    server.url + "api/panel/status", timeout=2
                ) as response:
                    status = json.load(response)
                self.assertEqual(status["panel"]["state"], "disconnected")
                with urllib.request.urlopen(
                    server.url + "api/media", timeout=2
                ) as response:
                    media = json.load(response)
                self.assertEqual(media["media"]["files"], ["library.png"])

                select_media = urllib.request.Request(
                    server.url + "api/media/select",
                    data=b'{"name":"library.png"}',
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Control-Token": status["token"],
                    },
                )
                with urllib.request.urlopen(select_media, timeout=2) as response:
                    selection = json.load(response)
                self.assertEqual(selection["panel"]["state"], "disconnected")
                self.assertEqual(selection["panel"]["selected_image"], "library.png")
                self.assertEqual(controller.media_select_calls, 1)

                upload_media = urllib.request.Request(
                    server.url + "api/media/upload",
                    data=b"synthetic image payload",
                    method="POST",
                    headers={
                        "Content-Type": "application/octet-stream",
                        "X-Control-Token": status["token"],
                        "X-Media-Name": "chosen.jpg",
                    },
                )
                with urllib.request.urlopen(upload_media, timeout=2) as response:
                    uploaded = json.load(response)
                self.assertEqual(uploaded["panel"]["state"], "disconnected")
                self.assertEqual(uploaded["panel"]["selected_image"], "chosen.jpg")
                self.assertEqual(controller.media_upload_calls, 1)
                self.assertEqual(controller.uploaded_data, b"synthetic image payload")
                with urllib.request.urlopen(
                    server.url + "api/panel/preview?layout=orientation", timeout=2
                ) as response:
                    self.assertEqual(response.read(), b"jpeg-preview")

                forbidden = urllib.request.Request(
                    server.url + "api/panel/detect",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(forbidden, timeout=2)
                self.assertEqual(context.exception.code, 403)
                context.exception.close()

                request = urllib.request.Request(
                    server.url + "api/panel/detect",
                    data=b"{}",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Control-Token": status["token"],
                    },
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    detected = json.load(response)
                self.assertEqual(detected["panel"]["state"], "detected")

                stop = urllib.request.Request(
                    server.url + "api/panel/stop",
                    data=b"{}",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Control-Token": status["token"],
                    },
                )
                with urllib.request.urlopen(stop, timeout=2) as response:
                    stopped = json.load(response)
                self.assertTrue(stopped["panel"]["can_restore_default"])

                unconfirmed = urllib.request.Request(
                    server.url + "api/panel/restore-default",
                    data=b"{}",
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Control-Token": status["token"],
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(unconfirmed, timeout=2)
                self.assertEqual(context.exception.code, 400)
                context.exception.close()
                self.assertEqual(controller.restore_calls, 0)

                restore = urllib.request.Request(
                    server.url + "api/panel/restore-default",
                    data=b'{"confirmed":true}',
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Control-Token": status["token"],
                    },
                )
                with urllib.request.urlopen(restore, timeout=2) as response:
                    restarting = json.load(response)
                self.assertEqual(restarting["panel"]["state"], "restarting")
                self.assertEqual(controller.restore_calls, 1)
            finally:
                server.httpd.shutdown()
                server.close()
                thread.join(timeout=2)
            self.assertTrue(controller.closed)


if __name__ == "__main__":
    unittest.main()
