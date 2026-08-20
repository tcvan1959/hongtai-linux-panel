import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hongtai_panel.config import AppConfig, load_config
from hongtai_panel.user_service import install_user_service, render_user_unit


class UserServiceTests(unittest.TestCase):
    def test_rendered_unit_uses_selected_python_and_config(self) -> None:
        unit = render_user_unit(
            python_executable="/opt/panel/python",
            config_path="/tmp/panel config.json",
            source_root="/opt/panel/src",
        )
        self.assertIn('"/opt/panel/python" -m hongtai_panel.cli_service', unit)
        self.assertIn('"/tmp/panel config.json"', unit)
        self.assertIn('Environment="PYTHONPATH=/opt/panel/src"', unit)
        self.assertIn("Restart=on-failure", unit)

    def test_install_writes_files_and_invokes_systemctl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            unit_path = root / "hongtai-linux-panel.service"
            runner = Mock()
            install_user_service(
                config=AppConfig(mode="dashboard"),
                config_path=config_path,
                unit_path=unit_path,
                python_executable="/opt/panel/python",
                source_root="/opt/panel/src",
                runner=runner,
            )
            installed_config = load_config(config_path)
            self.assertEqual(installed_config.mode, "dashboard")
            self.assertIsNotNone(installed_config.layout_path)
            assert installed_config.layout_path is not None
            self.assertTrue(Path(installed_config.layout_path).exists())
            self.assertIn("hongtai_panel.cli_service", unit_path.read_text())
            self.assertEqual(runner.call_count, 2)
            runner.assert_any_call(
                ["systemctl", "--user", "enable", "--now", "hongtai-linux-panel.service"],
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
