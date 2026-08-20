import subprocess
import tempfile
import unittest
from pathlib import Path

from hongtai_panel.metrics import (
    calculate_cpu_percent,
    read_cpu_times,
    read_hwmon_temperature,
    read_memory,
    read_nvidia_gpu,
)


class MetricsTests(unittest.TestCase):
    def test_cpu_times_and_percentage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stat"
            path.write_text("cpu  10 0 20 70 0 0 0 0 0 0\n", encoding="utf-8")
            self.assertEqual(read_cpu_times(str(path)), (70, 100))
        self.assertAlmostEqual(calculate_cpu_percent((70, 100), (80, 150)), 80.0)
        self.assertIsNone(calculate_cpu_percent(None, (80, 150)))

    def test_memory_usage_prefers_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "meminfo"
            path.write_text(
                "MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 250 kB\n",
                encoding="utf-8",
            )
            used, total, percent = read_memory(str(path))
        self.assertEqual(total, 1000 * 1024)
        self.assertEqual(used, 750 * 1024)
        self.assertEqual(percent, 75.0)

    def test_hwmon_prefers_requested_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            chip = Path(directory) / "hwmon2"
            chip.mkdir()
            (chip / "name").write_text("k10temp\n")
            (chip / "temp1_input").write_text("41000\n")
            (chip / "temp1_label").write_text("Tctl\n")
            (chip / "temp2_input").write_text("35000\n")
            (chip / "temp2_label").write_text("Tccd1\n")
            value = read_hwmon_temperature(
                "k10temp",
                preferred_labels=("Tctl",),
                hwmon_pattern=str(Path(directory) / "hwmon*"),
            )
        self.assertEqual(value, 41.0)

    def test_nvidia_csv_is_parsed(self) -> None:
        def runner(*_args, **_kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="RTX Test, 55, 42, 1024, 8192\n", stderr=""
            )

        gpu = read_nvidia_gpu(runner)
        self.assertIsNotNone(gpu)
        assert gpu is not None
        self.assertEqual(gpu[0], "RTX Test")
        self.assertEqual(gpu[1], 42.0)
        self.assertEqual(gpu[2], 55.0)
        self.assertEqual(gpu[3], 1024 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
