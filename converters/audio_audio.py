import os
from .base import BaseConverter
from .video_audio import _get_ffmpeg, _get_duration, _run_ffmpeg


class AudioToAudioConverter(BaseConverter):
    """
    Конвертация аудио → аудио через прямой вызов FFmpeg.
    Поддерживает: MP3, WAV, AAC, FLAC, OGG, WMA, M4A, AIFF, OPUS.
    """
    def _do_convert(self, progress_callback, check_cancel):
        duration = _get_duration(self.input_path)
        _, ext = os.path.splitext(self.output_path.lower())

        codec_map = {
            ".mp3":  ["-c:a", "libmp3lame", "-b:a", "192k"],
            ".wav":  ["-c:a", "pcm_s16le"],
            ".aac":  ["-c:a", "aac", "-b:a", "192k"],
            ".flac": ["-c:a", "flac"],
            ".ogg":  ["-c:a", "libvorbis", "-b:a", "192k"],
            ".wma":  ["-c:a", "wmav2", "-b:a", "192k"],
            ".m4a":  ["-c:a", "aac", "-b:a", "192k"],
            ".aiff": ["-c:a", "pcm_s16be"],
            ".opus": ["-c:a", "libopus", "-b:a", "128k"],
        }
        codec_args = codec_map.get(ext, ["-c:a", "libmp3lame", "-b:a", "192k"])

        args = [
            "-i", self.input_path,
            "-vn",
            *codec_args,
            self.output_path
        ]

        try:
            _run_ffmpeg(args, duration, progress_callback, check_cancel)
        except Exception as e:
            if os.path.exists(self.output_path):
                try:
                    os.remove(self.output_path)
                except Exception:
                    pass
            raise e
