#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import curses
import os
import sys
import subprocess
import time
import shlex
from typing import List, Tuple, Optional

# -----------------------------
# Configuration and constants
# -----------------------------
AUDIO_BR_STEPS = [64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384]  # common kbps values
# Audio formats/codecs accepted by YouTube (practical subset for uploads):
# Recommended: AAC-LC, 48 kHz. MP3 is also accepted; Opus is valid in WebM.
AUDIO_CODECS = [
    ("aac", "AAC-LC (recommended)"),
    ("libmp3lame", "MP3"),
    ("libopus", "Opus (WebM)"),
]
# Standard YouTube resolutions (width x height)
VIDEO_RESOLUTIONS = [
    ("426x240", "240p"),
    ("640x360", "360p"),
    ("854x480", "480p"),
    ("1280x720", "720p (HD)"),
    ("1920x1080", "1080p (FHD)"),
    ("2560x1440", "1440p (QHD)"),
    ("3840x2160", "2160p (4K)"),
]

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
AUD_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}


# -----------------------------
# Utilities
# -----------------------------
def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err


def ffprobe_audio_bitrate_kbps(path: str) -> Optional[int]:
    # Try to get the audio stream bit_rate first; if unavailable, fall back
    # to the container bit_rate.
    # 1) Stream bit rate
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=bit_rate",
        "-of",
        "default=nw=1:nk=1",
        path,
    ]
    rc, out, _ = run_cmd(cmd)
    bitrate = None
    if rc == 0 and out.strip().isdigit():
        try:
            bitrate = int(out.strip()) // 1000
        except Exception:
            bitrate = None
    if bitrate is None:
        # 2) Container bit rate
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=bit_rate",
            "-of",
            "default=nw=1:nk=1",
            path,
        ]
        rc, out, _ = run_cmd(cmd)
        if rc == 0 and out.strip().isdigit():
            try:
                bitrate = int(out.strip()) // 1000
            except Exception:
                bitrate = None
    return bitrate


def ffprobe_duration_sec(path: str) -> Optional[float]:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path]
    rc, out, _ = run_cmd(cmd)
    if rc == 0:
        try:
            return float(out.strip())
        except Exception:
            return None
    return None


def next_higher_bitrate(current_kbps: Optional[int]) -> int:
    if current_kbps is None:
        return 128  # safe default
    for value in AUDIO_BR_STEPS:
        if value > current_kbps:
            return value
    return AUDIO_BR_STEPS[-1]


def list_dir_entries(path: str, allowed_exts: Optional[set]) -> List[str]:
    try:
        items = os.listdir(path)
    except Exception:
        return []
    entries = []
    # Add navigation entry
    entries.append("..")
    for item in sorted(items):
        full = os.path.join(path, item)
        if os.path.isdir(full):
            entries.append(item + "/")
        else:
            if allowed_exts is None:
                entries.append(item)
            else:
                _, ext = os.path.splitext(item.lower())
                if ext in allowed_exts:
                    entries.append(item)
    return entries


def clamp(n, a, b):
    return max(a, min(n, b))


# -----------------------------
# Curses UI
# -----------------------------
class SimpleMenu:
    def __init__(self, stdscr, title: str, options: List[str], preselect: int = 0):
        self.stdscr = stdscr
        self.title = title
        self.options = options
        self.index = clamp(preselect, 0, max(0, len(options) - 1))

    def run(self) -> int:
        curses.curs_set(0)
        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            # Title
            self.stdscr.addnstr(0, 0, self.title[: w - 1], w - 1, curses.A_BOLD)
            # Instructions
            help_line = "Up/Down move, Enter select, q cancel"
            self.stdscr.addnstr(1, 0, help_line[: w - 1], w - 1, curses.A_DIM)
            # Options window
            start_row = 3
            visible_rows = h - start_row - 1
            top = clamp(self.index - visible_rows // 2, 0, max(0, len(self.options) - visible_rows))
            for i in range(visible_rows):
                idx = top + i
                if idx >= len(self.options):
                    break
                line = self.options[idx]
                attr = curses.A_REVERSE if idx == self.index else curses.A_NORMAL
                self.stdscr.addnstr(start_row + i, 0, line[: w - 1], w - 1, attr)
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord("q"), 27):
                return -1
            elif ch in (curses.KEY_UP, ord("k")):
                self.index = clamp(self.index - 1, 0, len(self.options) - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.index = clamp(self.index + 1, 0, len(self.options) - 1)
            elif ch in (curses.KEY_ENTER, 10, 13):
                return self.index


class FilePicker:
    def __init__(self, stdscr, start_path: str, title: str, allowed_exts: set):
        self.stdscr = stdscr
        self.cwd = os.path.abspath(start_path)
        self.title = title
        self.allowed_exts = allowed_exts
        self.entries = []
        self.index = 0

    def run(self) -> Optional[str]:
        curses.curs_set(0)
        while True:
            self.entries = list_dir_entries(self.cwd, self.allowed_exts)
            self.index = clamp(self.index, 0, max(0, len(self.entries) - 1))
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            self.stdscr.addnstr(0, 0, self.title[: w - 1], w - 1, curses.A_BOLD)
            path_line = f"Folder: {self.cwd}"
            self.stdscr.addnstr(1, 0, path_line[: w - 1], w - 1, curses.A_DIM)
            instruction = "Up/Down move, Enter open/select, Left back, q cancel"
            self.stdscr.addnstr(2, 0, instruction[: w - 1], w - 1, curses.A_DIM)
            start_row = 4
            visible_rows = h - start_row - 1
            top = clamp(self.index - visible_rows // 2, 0, max(0, len(self.entries) - visible_rows))
            for i in range(visible_rows):
                idx = top + i
                if idx >= len(self.entries):
                    break
                entry = self.entries[idx]
                attr = curses.A_REVERSE if idx == self.index else curses.A_NORMAL
                self.stdscr.addnstr(start_row + i, 0, entry[: w - 1], w - 1, attr)
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord("q"), 27):
                return None
            elif ch in (curses.KEY_UP, ord("k")):
                self.index = clamp(self.index - 1, 0, len(self.entries) - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.index = clamp(self.index + 1, 0, len(self.entries) - 1)
            elif ch in (curses.KEY_LEFT, 127, curses.KEY_BACKSPACE, 8):
                # Move up one folder
                self.cwd = os.path.abspath(os.path.join(self.cwd, ".."))
                self.index = 0
            elif ch in (curses.KEY_ENTER, 10, 13):
                choice = self.entries[self.index]
                if choice == "..":
                    self.cwd = os.path.abspath(os.path.join(self.cwd, ".."))
                    self.index = 0
                elif choice.endswith("/"):
                    self.cwd = os.path.join(self.cwd, choice[:-1])
                    self.index = 0
                else:
                    return os.path.join(self.cwd, choice)


# -----------------------------
# FFMPEG logic
# -----------------------------
def build_ffmpeg_cmd(
    image_path: str,
    audio_path: str,
    out_path: str,
    resolution: str,  # "1280x720"
    acodec: str,  # "aac", "libmp3lame", "libopus"
    abr_kbps: int,  # e.g., 192
    framerate: int = 30,
) -> List[str]:
    w, h = resolution.split("x")
    container = "mp4"
    vcodec = "libx264"
    extra_v = ["-tune", "stillimage", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-movflags", "+faststart"]
    # If Opus is selected, switch to VP9/WebM
    if acodec == "libopus":
        container = "webm"
        vcodec = "libvpx-vp9"
        # For still images, low/medium CRF with variable bitrate works well
        extra_v = ["-pix_fmt", "yuv420p", "-crf", "32", "-b:v", "0"]

    if not out_path.lower().endswith("." + container):
        out_path = os.path.splitext(out_path)[0] + "." + container

    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        str(framerate),
        "-i",
        image_path,
        "-i",
        audio_path,
        "-c:v",
        vcodec,
        "-vf",
        vf,
        *extra_v,
        "-c:a",
        acodec,
        "-b:a",
        f"{abr_kbps}k",
        "-ar",
        "48000",  # 48 kHz is the recommended sample rate
        "-shortest",
        # Progress to stdout
        "-progress",
        "pipe:1",
        "-nostats",
        out_path,
    ]
    return cmd


def format_seconds(s: float) -> str:
    if s < 0:
        s = 0
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


# -----------------------------
# Screen helpers
# -----------------------------
def show_message(stdscr, lines: List[str], footer: str = "Enter to continue, q to cancel") -> bool:
    curses.curs_set(0)
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        for i, line in enumerate(lines[: h - 2]):
            stdscr.addnstr(i, 0, line[: w - 1], w - 1, curses.A_BOLD if i == 0 else curses.A_NORMAL)
        stdscr.addnstr(h - 1, 0, footer[: w - 1], w - 1, curses.A_DIM)
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord("q"), 27):
            return False
        if ch in (curses.KEY_ENTER, 10, 13):
            return True


def progress_screen(stdscr, cmd: List[str], total_duration: Optional[float]) -> int:
    """
    Run ffmpeg while showing progress and ETA.
    Returns ffmpeg's return code.
    """
    curses.curs_set(0)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    out_time = 0.0
    speed = 1.0
    last_refresh = 0.0
    rc = None

    # Progress reading loop
    while True:
        line = proc.stdout.readline()
        if not line:
            # The process may have ended; exit if it has
            if proc.poll() is not None:
                rc = proc.returncode
                break
            time.sleep(0.05)
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "out_time_ms":
            try:
                out_time = int(val) / 1_000_000.0
            except Exception:
                pass
        elif key == "speed":
            try:
                # speed is usually reported like "1.23x"
                if val.endswith("x"):
                    speed = float(val[:-1])
            except Exception:
                pass

        now = time.time()
        if now - last_refresh >= 0.1:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            title = "Encoding with ffmpeg..."
            stdscr.addnstr(0, 0, title[: w - 1], w - 1, curses.A_BOLD)
            # Progress bar and percentage
            if total_duration and total_duration > 0:
                pct = clamp(out_time / total_duration, 0.0, 1.0)
                bar_width = max(w - 2, 1)
                filled = int(pct * bar_width)
                bar = "#" * filled + " " * (bar_width - filled)
                stdscr.addnstr(2, 0, f"[{bar}]", w - 1)
                stdscr.addnstr(3, 0, f"Progress: {int(pct * 100)}%", w - 1)
                # ETA
                remaining = max(total_duration - out_time, 0.0)
                eta = remaining / (speed if speed > 0 else 1.0)
                stdscr.addnstr(4, 0, f"Estimated time left: {format_seconds(eta)}", w - 1)
            else:
                stdscr.addnstr(2, 0, "Calculating duration...", w - 1)

            stdscr.addnstr(6, 0, f"Speed: {speed:.2f}x", w - 1, curses.A_DIM)
            cancel_msg = "Press q to cancel (it may take a few seconds)."
            stdscr.addnstr(h - 1, 0, cancel_msg[: w - 1], w - 1, curses.A_DIM)
            stdscr.refresh()
            last_refresh = now

        # Cancel if q is pressed
        stdscr.nodelay(True)
        ch = stdscr.getch()
        if ch in (ord("q"), 27):
            try:
                proc.terminate()
                time.sleep(0.2)
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            return 130  # canceled

    # Show final result
    stdscr.nodelay(False)
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    msg = "Completed!" if rc == 0 else f"ffmpeg exited with code {rc}"
    stdscr.addnstr(0, 0, msg[: w - 1], w - 1, curses.A_BOLD if rc == 0 else curses.A_NORMAL)
    stdscr.addnstr(h - 1, 0, "Enter to exit", w - 1, curses.A_DIM)
    stdscr.refresh()
    while True:
        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            break
    return rc


# -----------------------------
# Main flow
# -----------------------------
def main(stdscr):
    curses.use_default_colors()
    start_dir = os.getcwd()

    # 1) Select IMAGE
    img_picker = FilePicker(stdscr, start_dir, "Select the IMAGE (it will be used as a still video)", IMG_EXTS)
    img_path = img_picker.run()
    if not img_path:
        return
    if not os.path.exists(img_path):
        show_message(stdscr, ["Error", "Image not found."])
        return

    # 2) Select AUDIO
    aud_picker = FilePicker(stdscr, os.path.dirname(img_path), "Select the AUDIO file (mp3/wav/etc.)", AUD_EXTS)
    aud_path = aud_picker.run()
    if not aud_path:
        return
    if not os.path.exists(aud_path):
        show_message(stdscr, ["Error", "Audio file not found."])
        return

    # 3) Detect the audio bitrate and suggest a value
    opt_kbps = ffprobe_audio_bitrate_kbps(aud_path)
    dur_sec = ffprobe_duration_sec(aud_path)

    # YouTube recommendation info
    info_lines = [
        "YouTube audio recommendations:",
        "- Codec: AAC-LC (recommended).",
        "- Sample rate: 48 kHz.",
        "- Recommended bitrate (stereo): 128 kbps. For 5.1: 384 kbps.",
        "",
        f"Detected bitrate from your file: {opt_kbps} kbps" if opt_kbps else "Could not detect the bitrate from your file.",
    ]
    ok = show_message(stdscr, info_lines)
    if not ok:
        return

    # 4) Choose bitrate with preselection (next higher than detected)
    pre = 0
    pre_val = next_higher_bitrate(opt_kbps)
    br_opts = [f"{b} kbps" for b in AUDIO_BR_STEPS]
    if pre_val in AUDIO_BR_STEPS:
        pre = AUDIO_BR_STEPS.index(pre_val)
    br_menu = SimpleMenu(stdscr, "Choose the audio bitrate (Enter to select)", br_opts, preselect=pre)
    br_idx = br_menu.run()
    if br_idx < 0:
        return
    sel_br = AUDIO_BR_STEPS[br_idx]

    # 5) Choose audio codec/format
    ac_opts = [f"{codec[0]} - {codec[1]}" for codec in AUDIO_CODECS]
    # Default to AAC-LC
    ac_default = 0
    ac_menu = SimpleMenu(stdscr, "Choose the audio codec/format", ac_opts, preselect=ac_default)
    ac_idx = ac_menu.run()
    if ac_idx < 0:
        return
    acodec = AUDIO_CODECS[ac_idx][0]

    # 6) Choose video resolution
    vr_opts = [f"{resolution[1]} ({resolution[0]})" for resolution in VIDEO_RESOLUTIONS]
    # Suggest 1080p by default
    def_idx = 4  # 1080p
    vr_menu = SimpleMenu(stdscr, "Choose the video resolution", vr_opts, preselect=def_idx)
    vr_idx = vr_menu.run()
    if vr_idx < 0:
        return
    resolution = VIDEO_RESOLUTIONS[vr_idx][0]

    # 7) Confirmation and final output path
    # Determine container from the selected codec
    container = "webm" if acodec == "libopus" else "mp4"
    audio_name = os.path.splitext(os.path.basename(aud_path))[0]
    suggested_out = os.path.join(os.path.dirname(aud_path), f"{audio_name}.{container}")
    summary = [
        "Summary:",
        f"Image: {img_path}",
        f"Audio: {aud_path}",
        f"Audio bitrate: {sel_br} kbps",
        f"Audio codec: {acodec}",
        f"Resolution: {resolution}",
        f"Output: {suggested_out}",
        "",
        "A still-image video with scale/pad will be used for the selected resolution.",
        "Enter to start, q to cancel.",
    ]
    ok = show_message(stdscr, summary, footer="Enter to start, q to cancel")
    if not ok:
        return

    # 8) Build the ffmpeg command
    cmd = build_ffmpeg_cmd(
        image_path=img_path,
        audio_path=aud_path,
        out_path=suggested_out,
        resolution=resolution,
        acodec=acodec,
        abr_kbps=sel_br,
        framerate=30,
    )

    # 9) Progress
    rc = progress_screen(stdscr, cmd, total_duration=dur_sec)

    # 10) Final message with output path
    if rc == 0:
        show_message(stdscr, ["Done", f"File created: {suggested_out}"], footer="Enter to exit")
    elif rc == 130:
        show_message(stdscr, ["Canceled", "Process stopped by the user."], footer="Enter to exit")
    else:
        show_message(stdscr, ["Error", f"ffmpeg exited with code {rc}"], footer="Enter to exit")


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
