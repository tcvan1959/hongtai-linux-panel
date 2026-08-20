import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

from hongtai_panel.media import (
    ensure_private_media_dir,
    list_private_media,
    load_private_media,
    prepare_still_image,
)


def image_bytes(format_name="PNG", size=(64, 48), color="#22c55e"):
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format_name)
    return output.getvalue()


class MediaLibraryTests(unittest.TestCase):
    def test_private_media_directory_is_created_and_lists_stills_only(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory) / "nested" / "local"
            self.assertEqual(ensure_private_media_dir(media), media.resolve())
            (media / "b.JPG").write_bytes(image_bytes("JPEG"))
            (media / "a.png").write_bytes(image_bytes())
            (media / "notes.txt").write_text("private notes", encoding="utf-8")
            (media / "movie.gif").write_bytes(b"GIF89a")
            self.assertEqual(list_private_media(media), ["a.png", "b.JPG"])

    def test_png_and_jpeg_are_prepared_as_480_by_320_jpegs(self):
        for name, format_name in (("sample.png", "PNG"), ("sample.jpg", "JPEG")):
            with self.subTest(name=name):
                jpeg = prepare_still_image(image_bytes(format_name), name)
                with Image.open(BytesIO(jpeg)) as prepared:
                    self.assertEqual(prepared.format, "JPEG")
                    self.assertEqual(prepared.size, (480, 320))

    def test_fit_preserves_aspect_ratio_with_center_crop(self):
        source = Image.new("RGB", (800, 200), "#ef4444")
        for x in range(250, 550):
            for y in range(200):
                source.putpixel((x, y), (34, 197, 94))
        output = BytesIO()
        source.save(output, "PNG")
        jpeg = prepare_still_image(output.getvalue(), "wide.png")
        with Image.open(BytesIO(jpeg)) as prepared:
            red, green, blue = prepared.getpixel((240, 160))
            self.assertGreater(green, red)
            self.assertGreater(green, blue)
            edge_red, edge_green, _ = prepared.getpixel((5, 160))
            self.assertGreater(edge_green, edge_red)

    def test_unsupported_and_unreadable_files_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "only PNG and JPEG"):
            prepare_still_image(image_bytes("GIF"), "animation.gif")
        with self.assertRaisesRegex(ValueError, "only PNG and JPEG"):
            prepare_still_image(image_bytes("GIF"), "disguised.png")
        with self.assertRaisesRegex(ValueError, "not a readable"):
            prepare_still_image(b"not an image", "broken.png")

    def test_missing_traversal_and_read_failure_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            media = Path(directory)
            with self.assertRaises(FileNotFoundError):
                load_private_media(media, "missing.png")
            with self.assertRaisesRegex(ValueError, "single filename"):
                load_private_media(media, "../outside.png")
            image = media / "private.png"
            image.write_bytes(image_bytes())
            with mock.patch.object(
                Path,
                "read_bytes",
                side_effect=PermissionError("permission denied"),
            ):
                with self.assertRaisesRegex(OSError, "cannot read private image"):
                    load_private_media(media, image.name)

    def test_checkout_private_media_is_git_ignored(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / ".git").exists():
            self.skipTest("Git metadata is not present in this source tree")
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "display_media/local/private-test.png"],
            cwd=root,
            check=False,
        )
        marker = subprocess.run(
            ["git", "check-ignore", "-q", "display_media/local/.gitkeep"],
            cwd=root,
            check=False,
        )
        self.assertEqual(ignored.returncode, 0)
        self.assertNotEqual(marker.returncode, 0)

    def test_packaging_rules_prune_private_media(self):
        root = Path(__file__).resolve().parents[1]
        manifest = (root / "MANIFEST.in").read_text(encoding="utf-8")
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("include display_media/README.md", manifest)
        self.assertIn("prune display_media/local", manifest)
        self.assertIn('where = ["src"]', pyproject)
        self.assertFalse((root / "src" / "display_media").exists())


if __name__ == "__main__":
    unittest.main()
