# Media Converter

A Windows desktop application for converting video, audio, and images, as well as downloading YouTube videos as MP3 or MP4. The interface is built with Tkinter and uses the dark Catppuccin Mocha color palette.

> The app processes local files on the user's computer. An internet connection is only required to download a video from a YouTube link.

## Features

- Convert video to video, audio to audio, video to audio, and images to images.
- Progress tracking and cancellation for the current operation.
- Select an output folder and receive a warning before overwriting an existing file.
- Download YouTube videos as `MP3` (192 kbps) or `MP4`.
- FFmpeg is automatically provided through `imageio-ffmpeg`; no separate FFmpeg installation is needed.
- Build a standalone Windows application with PyInstaller.

## Supported formats

| Type | Formats |
| --- | --- |
| Video | `MP4`, `AVI`, `MKV`, `MOV`, `WEBM`, `FLV`, `WMV`, `TS`, `M4V` |
| Audio | `MP3`, `WAV`, `AAC`, `FLAC`, `OGG`, `WMA`, `M4A`, `AIFF`, `OPUS` |
| Images | `PNG`, `JPG`, `JPEG`, `BMP`, `GIF`, `TIFF`, `WEBP`, `ICO` |
| YouTube | Download as `MP3` or `MP4` |

Available output formats depend on the selected source file. For example, a video can be converted to audio, while an image cannot be converted to video.

## Quick start

Python 3.9+ with Tkinter is required.

```powershell
git clone <YOUR-REPOSITORY-URL>
cd convertor-master
py -m pip install Pillow imageio-ffmpeg yt-dlp
py app.py
```

If the `py` command is unavailable, use `python` instead.

## How to use

### Convert a local file

1. Open the **File Converter** tab.
2. Click **Select file** and choose a video, audio file, or image.
3. Select the output format — the list is generated automatically.
4. Change the destination folder if necessary.
5. Click **Convert**. When the task finishes, you can open the result folder.

The output file keeps the source file name and receives the new extension. If a file with that name already exists, the app asks for confirmation before overwriting it.

<img width="656" height="676" alt="image" src="https://github.com/user-attachments/assets/ea6225da-4eef-4fb2-bcbf-7487401f874c" />


### Download from YouTube

1. Open the **YouTube Converter** tab.
2. Paste a `youtube.com` or `youtu.be` video link.
3. Choose `MP3` or `MP4` and select an output folder.
4. Start the download.

Only download content you have the rights to use and follow YouTube's platform rules.

<img width="656" height="668" alt="image" src="https://github.com/user-attachments/assets/f6b8a96b-1117-49f4-87a1-94618147ccd6" />


## How it works

```text
Tkinter UI (app.py)
        │
        ├── ConverterManager ── selects a converter by file extension
        │       ├── VideoToAudioConverter ─┐
        │       ├── VideoToVideoConverter  ├── FFmpeg
        │       ├── AudioToAudioConverter  ┘
        │       └── ImageToImageConverter ─── Pillow
        │
        └── YoutubeDownloader ─── yt-dlp + FFmpeg
```

- `app.py` creates the interface, runs long operations in a background thread, and safely updates progress with `Tk.after`.
- `converters/manager.py` stores the allowed extension pairs and returns the appropriate converter class.
- Video and audio conversions use direct FFmpeg calls. Progress is read from `-progress pipe:1`, while cancellation stops the process.
- Compatible `MKV`, `MP4`, and `MOV` container pairs are first remuxed without re-encoding (`-c copy`). If that fails, the app re-encodes the file using H.264 + AAC.
- Images are processed with Pillow. When saving to formats without transparency support, transparent areas are replaced with a white background.
- `YoutubeDownloader` passes the bundled FFmpeg executable to `yt-dlp`: it extracts audio as MP3 or downloads and merges video and audio streams into MP4.

## Project structure

```text
.
├── app.py                    # UI and operation management
├── converters/
│   ├── base.py               # base converter interface
│   ├── manager.py            # format registry and converter selection
│   ├── video_audio.py        # video → audio and video → video via FFmpeg
│   ├── audio_audio.py        # audio → audio via FFmpeg
│   ├── image_image.py        # image conversion via Pillow
│   └── youtube.py            # YouTube downloads via yt-dlp
└── MediaConverter.spec       # PyInstaller build configuration
```

The `build/` and `dist/` folders are created during a build. The standalone Windows executable is located at `dist/MediaConverter.exe`.

## Build an `.exe`

Install PyInstaller and run:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm MediaConverter.spec
```

The executable will be created at `dist\MediaConverter.exe`.

## Technologies

- Python + Tkinter
- FFmpeg via `imageio-ffmpeg`
- Pillow
- yt-dlp
- PyInstaller

## Limitations

- Conversion is selected by file extension; damaged files or incompatible codecs may fail to process.
- Transparency is not preserved when converting to `JPG`, `BMP`, or `ICO`.
- YouTube download availability depends on the platform and the installed `yt-dlp` version. If there are issues, update it with: `py -m pip install -U yt-dlp`.
