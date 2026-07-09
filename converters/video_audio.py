import os
import re
import subprocess
import threading
import imageio_ffmpeg
from .base import BaseConverter


def _get_ffmpeg():
    """Возвращает путь к исполняемому файлу ffmpeg из imageio_ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()


def _get_duration(input_path):
    """Определяет длительность медиафайла в секундах через ffprobe/ffmpeg."""
    ffmpeg = _get_ffmpeg()
    try:
        result = subprocess.run(
            [ffmpeg, "-i", input_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        # ffmpeg выводит информацию в stderr
        output = result.stderr
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            h, m, s, ms = match.groups()
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 100
    except Exception:
        pass
    return 0


def _run_ffmpeg(args, duration, progress_callback, check_cancel):
    """
    Запускает FFmpeg с заданными аргументами и парсит прогресс из stderr.
    Это общая функция для всех типов конвертации.
    """
    ffmpeg = _get_ffmpeg()
    cmd = [ffmpeg, "-y", "-progress", "pipe:1", "-nostats"] + args

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace"
    )

    # Поток для чтения stderr (чтобы буфер не переполнился)
    stderr_lines = []
    def read_stderr():
        for line in process.stderr:
            stderr_lines.append(line)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()

    try:
        for line in process.stdout:
            # Проверяем отмену
            if check_cancel and check_cancel():
                process.kill()
                process.wait()
                raise InterruptedError("Конвертация отменена пользователем")

            # Парсим прогресс из вывода ffmpeg -progress
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    time_us = int(line.split("=")[1])
                    time_s = time_us / 1_000_000
                    if duration > 0 and progress_callback:
                        pct = min(99.0, (time_s / duration) * 100)
                        progress_callback(pct)
                except (ValueError, IndexError):
                    pass

        process.wait()

        if process.returncode != 0:
            err_text = "".join(stderr_lines[-20:])  # Последние 20 строк ошибок
            raise RuntimeError(f"FFmpeg завершился с ошибкой (код {process.returncode}):\n{err_text}")

        if progress_callback:
            progress_callback(100.0)

    except InterruptedError:
        raise
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
        raise


class VideoToAudioConverter(BaseConverter):
    """
    Быстрая конвертация видео → аудио через прямой вызов FFmpeg.
    Не декодирует видеокадры (-vn), что даёт ускорение в 5-20 раз по сравнению с moviepy.
    """
    def _do_convert(self, progress_callback, check_cancel):
        duration = _get_duration(self.input_path)

        _, ext = os.path.splitext(self.output_path.lower())

        # Подбираем кодек по расширению
        codec_map = {
            ".mp3": ["-c:a", "libmp3lame", "-b:a", "192k"],
            ".wav": ["-c:a", "pcm_s16le"],
            ".aac": ["-c:a", "aac", "-b:a", "192k"],
            ".flac": ["-c:a", "flac"],
            ".ogg": ["-c:a", "libvorbis", "-b:a", "192k"],
        }
        codec_args = codec_map.get(ext, ["-c:a", "libmp3lame", "-b:a", "192k"])

        args = [
            "-i", self.input_path,
            "-vn",              # Не обрабатывать видео — главный источник ускорения
            *codec_args,
            self.output_path
        ]

        try:
            _run_ffmpeg(args, duration, progress_callback, check_cancel)
        except Exception as e:
            # Удаляем недописанный файл
            if os.path.exists(self.output_path):
                try:
                    os.remove(self.output_path)
                except Exception:
                    pass
            raise e


class VideoToVideoConverter(BaseConverter):
    """
    Конвертация видео → видео через FFmpeg.
    Использует перекопирование потоков (-c copy) когда это возможно для мгновенной конвертации.
    Если формат контейнера несовместим с кодеками, перекодирует.
    """
    def _do_convert(self, progress_callback, check_cancel):
        duration = _get_duration(self.input_path)

        _, src_ext = os.path.splitext(self.input_path.lower())
        _, tgt_ext = os.path.splitext(self.output_path.lower())

        # Пары, в которых можно безопасно использовать -c copy (совместимые контейнеры)
        copy_compatible = {
            (".mkv", ".mp4"), (".mp4", ".mkv"),
            (".mov", ".mp4"), (".mp4", ".mov"),
            (".mov", ".mkv"), (".mkv", ".mov"),
        }

        if (src_ext, tgt_ext) in copy_compatible:
            # Мгновенная перемуксировка без перекодирования
            args = [
                "-i", self.input_path,
                "-c", "copy",
                self.output_path
            ]
        else:
            # Перекодирование в H.264 + AAC (универсальный совместимый формат)
            args = [
                "-i", self.input_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "192k",
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

            # Если -c copy упал, пробуем перекодировать
            if (src_ext, tgt_ext) in copy_compatible and "copy" in str(e):
                args = [
                    "-i", self.input_path,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "192k",
                    self.output_path
                ]
                try:
                    _run_ffmpeg(args, duration, progress_callback, check_cancel)
                except Exception as e2:
                    if os.path.exists(self.output_path):
                        try:
                            os.remove(self.output_path)
                        except Exception:
                            pass
                    raise e2
            else:
                raise e
