import json
import tempfile
import unittest
from pathlib import Path

from hongtai_panel.config import AppConfig, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            expected = AppConfig(mode="dashboard", update_interval=0.5)
            save_config(expected, path)
            self.assertEqual(load_config(path), expected)

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown"):
            AppConfig.from_dict({"mode": "dashboard", "typo": True})

    def test_image_mode_requires_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "image_path"):
            AppConfig(mode="image").validated()

    def test_unsupported_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "version"):
            AppConfig(version=99).validated()

    def test_invalid_interval_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "update_interval"):
            AppConfig(update_interval=61.0).validated()

    def test_dashboard_defaults_to_reduced_full_frame_rate(self) -> None:
        config = AppConfig().validated()
        self.assertEqual(config.update_interval, 30.0)
        self.assertEqual(config.jpeg_quality, 55)

    def test_fail_stop_is_the_safe_default(self) -> None:
        self.assertFalse(AppConfig().validated().reconnect_enabled)

    def test_reconnect_flag_must_be_boolean(self) -> None:
        with self.assertRaisesRegex(ValueError, "reconnect_enabled"):
            AppConfig(reconnect_enabled="yes").validated()

    def test_non_object_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps([]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON object"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
