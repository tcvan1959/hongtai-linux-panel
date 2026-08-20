import unittest
from datetime import datetime
from io import BytesIO

from PIL import Image

from hongtai_panel.dashboard import render_dashboard
from hongtai_panel.metrics import SystemMetrics
from hongtai_panel.rendering import encode_jpeg


class DashboardTests(unittest.TestCase):
    def test_dashboard_renders_to_panel_geometry(self) -> None:
        metrics = SystemMetrics(
            captured_at=datetime(2026, 8, 17, 8, 30, 15),
            cpu_percent=37.0,
            cpu_temp_c=42.5,
            memory_percent=31.0,
            memory_used_bytes=10 * 1024**3,
            memory_total_bytes=32 * 1024**3,
            gpu_name="AMD GPU",
            gpu_percent=9.0,
            gpu_temp_c=36.0,
            gpu_memory_used_bytes=20 * 1024**2,
            gpu_memory_total_bytes=512 * 1024**2,
        )
        jpeg = encode_jpeg(render_dashboard(metrics))
        with Image.open(BytesIO(jpeg)) as image:
            self.assertEqual(image.size, (480, 320))

    def test_dashboard_tolerates_unavailable_metrics(self) -> None:
        metrics = SystemMetrics(
            captured_at=datetime(2026, 8, 17),
            cpu_percent=None,
            cpu_temp_c=None,
            memory_percent=None,
            memory_used_bytes=None,
            memory_total_bytes=None,
            gpu_name=None,
            gpu_percent=None,
            gpu_temp_c=None,
            gpu_memory_used_bytes=None,
            gpu_memory_total_bytes=None,
        )
        self.assertEqual(render_dashboard(metrics).size, (480, 320))


if __name__ == "__main__":
    unittest.main()
