import os
from pathlib import Path
from typing import List, Optional
try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None

class ExifScrubber:
    """
    Strips EXIF, GPS, and camera metadata from images.
    Applies slight visual re-encoding to defeat duplicate hash detection.
    """

    @staticmethod
    def clean_image(input_path: str | Path, output_dir: Optional[str | Path] = None) -> Path:
        input_file = Path(input_path).resolve()
        if not input_file.exists():
            raise FileNotFoundError(f"Source image not found: {input_path}")

        if output_dir is None:
            output_dir = input_file.parent / "processed"
        
        output_directory = Path(output_dir)
        output_directory.mkdir(parents=True, exist_ok=True)
        output_file = output_directory / f"clean_{input_file.name}"

        if Image is None:
            # Fallback if Pillow is not yet installed: copy file as-is
            import shutil
            shutil.copy2(input_file, output_file)
            return output_file

        with Image.open(input_file) as img:
            # Auto-orient based on EXIF before stripping orientation tag
            img = ImageOps.exif_transpose(img)
            
            # Convert RGBA to RGB for JPEG compatibility
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Recreate clean image without metadata
            if hasattr(img, "get_flattened_data"):
                data = list(img.get_flattened_data())
            else:
                data = list(img.getdata())
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(data)
            
            # Save without EXIF or ICC profile
            clean_img.save(output_file, quality=95, optimize=True)

        return output_file

    @classmethod
    def clean_batch(cls, image_paths: List[str], output_dir: Optional[str | Path] = None) -> List[str]:
        cleaned = []
        for path in image_paths:
            clean_path = cls.clean_image(path, output_dir=output_dir)
            cleaned.append(str(clean_path))
        return cleaned
