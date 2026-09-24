import unittest
import tempfile
from pathlib import Path
from payload.exif_scrubber import ExifScrubber

class TestExifScrubber(unittest.TestCase):
    def test_scrubber_cleaning(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed in test environment")

        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "sample.jpg"
            img = Image.new("RGB", (100, 100), color="blue")
            img.save(img_path)

            clean_file = ExifScrubber.clean_image(img_path, output_dir=Path(tmpdir) / "out")
            self.assertTrue(Path(clean_file).exists())
            self.assertGreater(clean_file.stat().st_size, 0)

if __name__ == "__main__":
    unittest.main()
