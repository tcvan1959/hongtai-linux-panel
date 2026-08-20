import unittest
from io import BytesIO

from PIL import Image

from hongtai_panel.protocol import MAX_JPEG_BYTES
from hongtai_panel.rendering import encode_jpeg, render_test_pattern


class RenderingTests(unittest.TestCase):
    def test_pattern_geometry_and_jpeg_budget(self) -> None:
        image = render_test_pattern(480, 320)
        self.assertEqual(image.size, (480, 320))
        jpeg = encode_jpeg(image)
        self.assertLessEqual(len(jpeg), MAX_JPEG_BYTES)
        with Image.open(BytesIO(jpeg)) as decoded:
            self.assertEqual(decoded.size, (480, 320))
            self.assertEqual(decoded.format, "JPEG")

    def test_invalid_quality_range_is_rejected(self) -> None:
        image = Image.new("RGB", (10, 10))
        with self.assertRaises(ValueError):
            encode_jpeg(image, quality=20, min_quality=30)

    def test_pattern_accepts_model_and_changing_status(self) -> None:
        image = render_test_pattern(480, 320, model="model-x", status="12:34:56")
        self.assertEqual(image.size, (480, 320))


if __name__ == "__main__":
    unittest.main()
