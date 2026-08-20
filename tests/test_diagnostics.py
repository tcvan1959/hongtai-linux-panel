import threading
import subprocess
import tempfile
import unittest
from pathlib import Path

from hongtai_panel.diagnostics import HostHealthCheck, ReplyCapture, WriteCapture
from hongtai_panel.protocol import CMD_REFRESH, build_command
from hongtai_panel.service import DynamicDisplayService


class ChunkPanel:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks

    def queued_input_bytes(self) -> int:
        return len(self.chunks[0]) if self.chunks else 0

    def read_available(self, *, timeout: float = 0.0, limit: int = 64 * 1024) -> bytes:
        return self.chunks.pop(0)[:limit] if self.chunks else b""


class ReplyCaptureTests(unittest.TestCase):
    def test_split_framed_reply_is_reassembled_and_validated(self) -> None:
        raw = build_command(CMD_REFRESH, b"\x01")
        panel = ChunkPanel([raw[:3], raw[3:]])
        capture = ReplyCapture()
        self.assertEqual(capture.poll(panel, "first").frames, ())
        event = capture.poll(panel, "second")
        self.assertEqual(len(event.frames), 1)
        self.assertEqual(event.frames[0].command, CMD_REFRESH)
        self.assertEqual(event.frames[0].payload, b"\x01")
        summary = capture.summary()
        self.assertEqual(summary["frame_count"], 1)
        self.assertEqual(summary["by_operation"]["second"]["frames"], 1)
        self.assertEqual(summary["frame_samples"][0]["command"], "0x11")
        self.assertEqual(summary["frame_samples"][0]["payload_hex"], "01")

    def test_unframed_bytes_are_counted_and_sampled(self) -> None:
        capture = ReplyCapture(max_sample_bytes=4)
        capture.poll(ChunkPanel([b"noise"]), "noise")
        self.assertEqual(capture.total_bytes, 5)
        self.assertEqual(capture.malformed_bytes, 5)
        self.assertEqual(capture.summary()["sample_hex"], "6e 6f 69 73")

    def test_bounded_service_captures_replies_and_stops(self) -> None:
        stop = threading.Event()
        response = build_command(CMD_REFRESH, b"\x01")

        class DiagnosticPanel:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def send_jpeg(self, _jpeg: bytes, **_options) -> None:
                return None

            def refresh(self) -> None:
                return None

            def queued_input_bytes(self) -> int:
                return len(response)

            def read_available(
                self, *, timeout: float = 0.0, limit: int = 64 * 1024
            ) -> bytes:
                return response[:limit]

        capture = ReplyCapture()
        service = DynamicDisplayService(
            lambda: b"frame",
            frame_interval=1.0,
            refresh_interval=0.001,
            reconnect=False,
            reply_capture=capture,
            session_limit=0.005,
            panel_factory=lambda _path: DiagnosticPanel(),
            path_resolver=lambda _explicit: "/dev/test-panel",
        )
        service.run(stop)
        self.assertTrue(stop.is_set())
        self.assertGreaterEqual(capture.frame_count, 2)
        self.assertGreaterEqual(capture.high_water_bytes, len(response))

    def test_session_limit_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "session_limit"):
            DynamicDisplayService(lambda: b"frame", session_limit=1801)

    def test_write_capture_summarizes_successes_and_errors(self) -> None:
        capture = WriteCapture()
        capture.record(10, 0.01)
        capture.record(20, 0.03)
        capture.record(30, 0.75, TimeoutError("stalled"))
        summary = capture.summary()
        self.assertEqual(summary["write_count"], 3)
        self.assertEqual(summary["successful_write_count"], 2)
        self.assertEqual(summary["error_count"], 1)
        self.assertEqual(summary["total_bytes"], 60)
        self.assertEqual(summary["median_seconds"], 0.02)
        self.assertEqual(summary["max_seconds"], 0.75)
        self.assertIn("TimeoutError: stalled", summary["errors"])

    def test_host_health_check_detects_kernel_usb_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tty = Path(directory, "ttyACM0")
            tty.touch()

            def runner(*_args, **_kwargs):
                return subprocess.CompletedProcess(
                    [], 0, stdout="usb 9-9: USB disconnect, device number 5\n", stderr=""
                )

            check = HostHealthCheck(str(tty), "9-9", runner=runner)
            with self.assertRaisesRegex(RuntimeError, "kernel event"):
                check()

    def test_host_health_check_detects_tty_loss_without_querying_kernel(self) -> None:
        check = HostHealthCheck(
            "/missing/ttyACM0",
            "9-9",
            runner=lambda *_args, **_kwargs: self.fail("runner should not be called"),
        )
        with self.assertRaisesRegex(RuntimeError, "tty disappeared"):
            check()


if __name__ == "__main__":
    unittest.main()
