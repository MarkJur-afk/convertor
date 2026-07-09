import os
from typing import Dict, Type, Tuple, List
from .base import BaseConverter
from .video_audio import VideoToAudioConverter, VideoToVideoConverter
from .audio_audio import AudioToAudioConverter
from .image_image import ImageToImageConverter

class ConverterManager:
    """
    Класс для управления регистрацией и выбором нужного конвертера.
    """
    def __init__(self):
        self._registry: Dict[Tuple[str, str], Type[BaseConverter]] = {}
        
        # ===== Форматы =====
        video_formats = ['.mp4', '.avi', '.mkv', '.mov', '.webm', '.flv', '.wmv', '.ts', '.m4v']
        audio_formats = ['.mp3', '.wav', '.aac', '.flac', '.ogg', '.wma', '.m4a', '.aiff', '.opus']
        image_formats = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp', '.ico']

        # ===== Видео → Аудио =====
        for v in video_formats:
            for a in audio_formats:
                self.register_converter(v, a, VideoToAudioConverter)

        # ===== Видео → Видео =====
        for src in video_formats:
            for tgt in video_formats:
                if src != tgt:
                    self.register_converter(src, tgt, VideoToVideoConverter)

        # ===== Аудио → Аудио =====
        for src in audio_formats:
            for tgt in audio_formats:
                if src != tgt:
                    self.register_converter(src, tgt, AudioToAudioConverter)

        # ===== Изображение → Изображение =====
        for src in image_formats:
            for tgt in image_formats:
                # .jpg и .jpeg — одно и то же, не конвертируем между ними
                if src != tgt and not ({src, tgt} == {'.jpg', '.jpeg'}):
                    self.register_converter(src, tgt, ImageToImageConverter)

    def register_converter(self, source_ext: str, target_ext: str, converter_cls: Type[BaseConverter]):
        src = source_ext.lower().strip()
        if src and not src.startswith('.'):
            src = '.' + src
        tgt = target_ext.lower().strip()
        if tgt and not tgt.startswith('.'):
            tgt = '.' + tgt
        self._registry[(src, tgt)] = converter_cls

    def get_supported_targets(self, source_path: str) -> List[str]:
        _, ext = os.path.splitext(source_path.lower())
        targets = []
        for src, tgt in self._registry.keys():
            if src == ext:
                targets.append(tgt)
        return sorted(list(set(targets)))

    def get_converter(self, input_path: str, target_ext: str, output_path: str = None) -> BaseConverter:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Исходный файл не найден: {input_path}")
            
        _, src_ext = os.path.splitext(input_path.lower())
        tgt = target_ext.lower().strip()
        if tgt and not tgt.startswith('.'):
            tgt = '.' + tgt
            
        pair = (src_ext, tgt)
        if pair not in self._registry:
            raise ValueError(f"Конвертация из {src_ext} в {tgt} не поддерживается.")
            
        converter_cls = self._registry[pair]
        
        if output_path is None:
            output_dir = os.path.dirname(input_path)
            base_name, _ = os.path.splitext(os.path.basename(input_path))
            output_path = os.path.join(output_dir, f"{base_name}{tgt}")
            
        return converter_cls(input_path, output_path)

manager = ConverterManager()
