import os
from PIL import Image
from .base import BaseConverter


class ImageToImageConverter(BaseConverter):
    """
    Конвертация изображений через Pillow.
    Поддерживает: PNG, JPG/JPEG, BMP, GIF, TIFF, WEBP, ICO.
    """
    def _do_convert(self, progress_callback, check_cancel):
        if progress_callback:
            progress_callback(10.0)

        if check_cancel and check_cancel():
            raise InterruptedError("Конвертация отменена пользователем")

        img = Image.open(self.input_path)

        if progress_callback:
            progress_callback(40.0)

        _, ext = os.path.splitext(self.output_path.lower())

        # Конвертируем RGBA → RGB для форматов, не поддерживающих прозрачность
        no_alpha_formats = {".jpg", ".jpeg", ".bmp", ".ico"}
        if ext in no_alpha_formats and img.mode in ("RGBA", "LA", "PA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif ext in no_alpha_formats and img.mode != "RGB":
            img = img.convert("RGB")

        if check_cancel and check_cancel():
            raise InterruptedError("Конвертация отменена пользователем")

        if progress_callback:
            progress_callback(70.0)

        # Параметры сохранения для каждого формата
        save_kwargs = {}
        if ext in (".jpg", ".jpeg"):
            save_kwargs = {"quality": 95, "optimize": True}
        elif ext == ".png":
            save_kwargs = {"optimize": True}
        elif ext == ".webp":
            save_kwargs = {"quality": 90, "method": 4}
        elif ext == ".tiff":
            save_kwargs = {"compression": "tiff_lzw"}
        elif ext == ".ico":
            # ICO поддерживает ограниченные размеры
            sizes = [(min(img.width, 256), min(img.height, 256))]
            img = img.resize(sizes[0], Image.LANCZOS)
            save_kwargs = {}
        elif ext == ".gif":
            if img.mode != "P" and img.mode != "RGB":
                img = img.convert("RGB")

        try:
            img.save(self.output_path, **save_kwargs)
        except Exception as e:
            if os.path.exists(self.output_path):
                try:
                    os.remove(self.output_path)
                except Exception:
                    pass
            raise e

        if progress_callback:
            progress_callback(100.0)
