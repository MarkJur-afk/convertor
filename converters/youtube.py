import os
import imageio_ffmpeg

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class YoutubeDownloader:
    """
    Класс для скачивания и конвертации видео с YouTube с помощью yt-dlp.
    """
    def __init__(self, url: str, output_dir: str, format_type: str):
        self.url = url
        self.output_dir = output_dir
        self.format_type = format_type.lower().replace(".", "").strip() # "mp3" или "mp4"

    def download(self, progress_callback=None, check_cancel=None):
        if yt_dlp is None:
            raise ImportError("Библиотека yt-dlp не установлена. Пожалуйста, подождите или установите её.")

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Список для отслеживания путей к созданным временным файлам для их последующего удаления при отмене
        downloaded_temp_files = []

        def ytdl_hook(d):
            if check_cancel and check_cancel():
                # Запоминаем временный файл, если он есть
                filename = d.get('filename')
                if filename and filename not in downloaded_temp_files:
                    downloaded_temp_files.append(filename)
                
                # Добавляем .part версию
                part_filename = filename + '.part' if filename else None
                if part_filename and part_filename not in downloaded_temp_files:
                    downloaded_temp_files.append(part_filename)

                raise InterruptedError("Загрузка отменена пользователем")

            if d['status'] == 'downloading':
                # Считаем процент скачивания
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                
                # Сохраняем имя временного файла
                filename = d.get('filename')
                if filename and filename not in downloaded_temp_files:
                    downloaded_temp_files.append(filename)
                
                if total:
                    pct = (downloaded / total) * 100
                    # Масштабируем: скачивание - это 85% всего процесса
                    if progress_callback:
                        progress_callback(pct * 0.85)
                        
            elif d['status'] == 'finished':
                # Фиксируем итоговое имя файла
                filename = d.get('filename')
                if filename and filename not in downloaded_temp_files:
                    downloaded_temp_files.append(filename)
                    
                if progress_callback:
                    progress_callback(85.0)

        class CustomYtdlLogger:
            def debug(self, msg):
                # Отслеживаем этапы постобработки (конвертация, объединение видео и аудио)
                if progress_callback:
                    if "Extracting audio" in msg or "Converting" in msg:
                        progress_callback(90.0)
                    elif "Merging" in msg:
                        progress_callback(95.0)
            def warning(self, msg):
                pass
            def error(self, msg):
                pass

        ydl_opts = {
            'ffmpeg_location': ffmpeg_path,
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'progress_hooks': [ytdl_hook],
            'logger': CustomYtdlLogger(),
            'noprogress': True,
            'quiet': True,
        }

        if self.format_type == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else: # mp4
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Если скачивали mp3, yt-dlp конвертирует исходное расширение (m4a/webm) в mp3
                if self.format_type == 'mp3':
                    base, _ = os.path.splitext(filename)
                    final_path = f"{base}.mp3"
                else:
                    final_path = filename

                if progress_callback:
                    progress_callback(100.0)

                return final_path
                
        except Exception as e:
            # При ошибке или отмене подчищаем все временные файлы
            for f in downloaded_temp_files:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
                
                # Дополнительно пытаемся почистить файлы с расширением .part
                if f and not f.endswith('.part'):
                    part_f = f + '.part'
                    if os.path.exists(part_f):
                        try:
                            os.remove(part_f)
                        except Exception:
                            pass
            raise e
