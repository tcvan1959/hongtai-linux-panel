import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from hongtai_panel.layout import LiveLayout, Layout, Widget, default_layout_path, load_layout
from hongtai_panel.layout_renderer import render_layout
from hongtai_panel.metrics import SystemMetrics
from hongtai_panel.rendering import encode_jpeg


def sample_metrics() -> SystemMetrics:
    return SystemMetrics(
        captured_at=datetime(2026, 8, 17, 9, 15, 30),
        cpu_percent=25.0,
        cpu_temp_c=41.0,
        memory_percent=37.0,
        memory_used_bytes=12 * 1024**3,
        memory_total_bytes=32 * 1024**3,
        gpu_name="AMD GPU",
        gpu_percent=8.0,
        gpu_temp_c=36.0,
        gpu_memory_used_bytes=16 * 1024**2,
        gpu_memory_total_bytes=512 * 1024**2,
    )


class LayoutTests(unittest.TestCase):
    def test_default_layout_validates_and_renders(self) -> None:
        layout = load_layout(default_layout_path())
        self.assertEqual(layout.name, "System monitor starter dashboard")
        self.assertGreater(len(layout.widgets), 10)
        image = render_layout(layout, sample_metrics())
        self.assertEqual(image.size, (480, 320))
        self.assertLess(len(encode_jpeg(image)), 80 * 1024)

    def test_widget_outside_canvas_is_rejected(self) -> None:
        layout = Layout(
            width=100,
            height=100,
            widgets=(Widget(kind="label", x=90, y=0, width=20, height=10, text="x"),),
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            layout.validated()

    def test_unknown_widget_field_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown widget"):
            Layout.from_dict(
                {
                    "widgets": [
                        {
                            "kind": "label",
                            "x": 0,
                            "y": 0,
                            "width": 10,
                            "height": 10,
                            "text": "x",
                            "typo": 1,
                        }
                    ]
                }
            )

    def test_live_reload_retains_last_valid_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            valid = {
                "version": 1,
                "name": "Valid",
                "width": 100,
                "height": 100,
                "widgets": [],
            }
            path.write_text(json.dumps(valid), encoding="utf-8")
            watcher = LiveLayout(path)
            first = watcher.get()
            first_mtime = path.stat().st_mtime_ns
            path.write_text("{ invalid", encoding="utf-8")
            os.utime(path, ns=(first_mtime + 1_000_000, first_mtime + 1_000_000))
            with self.assertLogs("hongtai_panel.layout", level="WARNING"):
                second = watcher.get()
            self.assertIs(second, first)

    def test_missing_metric_renders_placeholder(self) -> None:
        widget = Widget(
            kind="value",
            x=0,
            y=0,
            width=100,
            height=30,
            source="cpu_percent",
            format="{value:.0f}%",
        )
        metrics = sample_metrics()
        metrics = SystemMetrics(
            captured_at=metrics.captured_at,
            cpu_percent=None,
            cpu_temp_c=metrics.cpu_temp_c,
            memory_percent=metrics.memory_percent,
            memory_used_bytes=metrics.memory_used_bytes,
            memory_total_bytes=metrics.memory_total_bytes,
            gpu_name=metrics.gpu_name,
            gpu_percent=metrics.gpu_percent,
            gpu_temp_c=metrics.gpu_temp_c,
            gpu_memory_used_bytes=metrics.gpu_memory_used_bytes,
            gpu_memory_total_bytes=metrics.gpu_memory_total_bytes,
        )
        layout = Layout(width=100, height=30, widgets=(widget,)).validated()
        self.assertEqual(render_layout(layout, metrics).size, (100, 30))


if __name__ == "__main__":
    unittest.main()
