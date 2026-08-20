import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from hongtai_panel.editor import EditorStore, create_editor_server


def sample_layout(name: str = "Editor test") -> dict:
    return {
        "version": 1,
        "name": name,
        "width": 480,
        "height": 320,
        "background": "#080d18",
        "widgets": [
            {
                "kind": "label",
                "x": 10,
                "y": 10,
                "width": 120,
                "height": 30,
                "text": "Hello",
            }
        ],
    }


class EditorStoreTests(unittest.TestCase):
    def test_save_validates_and_replaces_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            path.write_text(json.dumps(sample_layout()), encoding="utf-8")
            store = EditorStore(path)
            changed = sample_layout("Changed")
            self.assertEqual(store.save_dict(changed)["name"], "Changed")
            self.assertEqual(store.load_dict()["name"], "Changed")
            self.assertFalse(any(path.parent.glob(".layout.json.*.tmp")))

    def test_invalid_save_preserves_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            original = sample_layout()
            path.write_text(json.dumps(original), encoding="utf-8")
            changed = sample_layout("Invalid")
            changed["widgets"][0]["x"] = 999
            with self.assertRaisesRegex(ValueError, "outside"):
                EditorStore(path).save_dict(changed)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)

    def test_remote_bind_address_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "localhost"):
            create_editor_server("unused.json", host="0.0.0.0")


class EditorHttpTests(unittest.TestCase):
    def test_editor_serves_and_requires_token_to_save(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            path.write_text(json.dumps(sample_layout()), encoding="utf-8")
            server = create_editor_server(path, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urllib.request.urlopen(server.url, timeout=2) as response:
                    self.assertIn(b"Panel Studio", response.read())
                with urllib.request.urlopen(server.url + "api/layout", timeout=2) as response:
                    result = json.load(response)
                self.assertEqual(result["layout"]["name"], "Editor test")
                request = urllib.request.Request(
                    server.url + "api/layout",
                    data=json.dumps(sample_layout("Saved through API")).encode(),
                    method="PUT",
                    headers={
                        "Content-Type": "application/json",
                        "X-Editor-Token": result["token"],
                    },
                )
                with urllib.request.urlopen(request, timeout=2) as response:
                    saved = json.load(response)
                self.assertTrue(saved["saved"])
                self.assertEqual(EditorStore(path).load_dict()["name"], "Saved through API")

                forbidden = urllib.request.Request(
                    server.url + "api/layout",
                    data=json.dumps(sample_layout()).encode(),
                    method="PUT",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as context:
                    urllib.request.urlopen(forbidden, timeout=2)
                self.assertEqual(context.exception.code, 403)
                context.exception.close()
            finally:
                server.httpd.shutdown()
                server.close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
