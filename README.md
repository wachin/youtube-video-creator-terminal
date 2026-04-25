# YouTube Video Creator (Terminal)

---

Tutorial en español aquí: 
[README_ES.md](README_ES.md)

---

![Python](https://img.shields.io/badge/Python-3.x-blue)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-brightgreen)
![Interface](https://img.shields.io/badge/UI-Terminal%20(curses)-orange)
![Output](https://img.shields.io/badge/Output-MP4%20%7C%20WebM-red)

Create a simple video for YouTube from a single image and an audio file directly in the terminal.

This project provides a `curses`-based interface that lets you pick an image, choose an audio track, select encoding options, and render a final video with `ffmpeg`.

## Features

- Turn one still image plus one audio file into a video.
- Browse files from the terminal with an interactive picker.
- Detect the source audio bitrate with `ffprobe`.
- Choose the audio bitrate, codec, and target video resolution.
- Generate `MP4` output for AAC/MP3 or `WebM` output for Opus.
- Show encoding progress, speed, and estimated remaining time.

## Requirements

- Python 3
- `ffmpeg`
- `ffprobe`
- A terminal environment with Python `curses` support

## Supported Input Formats

### Images

`jpg`, `jpeg`, `png`, `bmp`, `webp`

### Audio

`mp3`, `wav`, `m4a`, `aac`, `flac`, `ogg`, `opus`, `wma`

## How It Works

1. Select a still image.
2. Select an audio file.
3. Review YouTube-oriented audio recommendations.
4. Pick an audio bitrate.
5. Pick an audio codec.
6. Pick a video resolution.
7. Confirm the summary and start encoding.

The script then builds an `ffmpeg` command that loops the image, matches the output length to the audio, and exports a ready-to-upload video file.

## Usage

Run:

```bash
python3 yt_creator.py
```

## Controls

- `Up` / `Down`: move through options
- `Enter`: select
- `Left` / `Backspace`: go up one directory in the file picker
- `q` or `Esc`: cancel

## Output

- Default container: `MP4`
- If `libopus` is selected, output switches to `WebM`
- Output file name format:

```text
output_<timestamp>.mp4
output_<timestamp>.webm
```

The generated file is saved in the same directory as the selected audio file.

## Notes

- The script is focused on local video generation only.
- It does not upload videos to YouTube.
- Audio is encoded at `48 kHz`, which aligns with common YouTube recommendations.
- For non-Opus output, video is encoded with `libx264`.

## Project File

- `yt_creator.py`: main terminal application
