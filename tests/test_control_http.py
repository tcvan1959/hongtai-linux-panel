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
            "layouts": {"orientation": "Orientation test"},
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
                with urllib.request.urlopen(
                    server.url + "control.js", timeout=2
                ) as response:
                    control_js = response.read()
                self.assertIn(b"window.confirm", control_js)
                self.assertIn(b"/api/panel/restore-default", control_js)
                with urllib.request.urlopen(
                    server.url + "api/panel/status", timeout=2
                ) as response:
                    status = json.load(response)
                self.assertEqual(status["panel"]["state"], "disconnected")
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
