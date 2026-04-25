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
# Configuración y constantes
# -----------------------------
AUDIO_BR_STEPS = [64, 96, 128, 160, 192, 256, 320, 384]  # kbps típicos
# Formatos/Codecs de audio que acepta YouTube (subconjunto práctico para uploads):
# Recomendado: AAC-LC, 48 kHz. Acepta también MP3; Opus es válido en WebM.
AUDIO_CODECS = [
    ("aac", "AAC-LC (recomendado)"),
    ("libmp3lame", "MP3"),
    ("libopus", "Opus (WebM)"),
]
# Resoluciones estándar de YouTube (ancho x alto)
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
# Utilidades
# -----------------------------
def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = p.communicate()
    return p.returncode, out, err

def ffprobe_audio_bitrate_kbps(path: str) -> Optional[int]:
    # Intentar obtener bit_rate del stream de audio; si no, del contenedor
    # 1) Por stream
    cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0",
           "-show_entries", "stream=bit_rate", "-of", "default=nw=1:nk=1", path]
    rc, out, _ = run_cmd(cmd)
    br = None
    if rc == 0 and out.strip().isdigit():
        try:
            br = int(out.strip()) // 1000
        except:
            br = None
    if br is None:
        # 2) Por formato
        cmd = ["ffprobe", "-v", "error",
               "-show_entries", "format=bit_rate", "-of", "default=nw=1:nk=1", path]
        rc, out, _ = run_cmd(cmd)
        if rc == 0 and out.strip().isdigit():
            try:
                br = int(out.strip()) // 1000
            except:
                br = None
    return br

def ffprobe_duration_sec(path: str) -> Optional[float]:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", path]
    rc, out, _ = run_cmd(cmd)
    if rc == 0:
        try:
            return float(out.strip())
        except:
            return None
    return None

def next_higher_bitrate(current_kbps: Optional[int]) -> int:
    if current_kbps is None:
        return 128  # default seguro
    for val in AUDIO_BR_STEPS:
        if val > current_kbps:
            return val
    return AUDIO_BR_STEPS[-1]

def list_dir_entries(path: str, allowed_exts: Optional[set]) -> List[str]:
    try:
        items = os.listdir(path)
    except Exception:
        return []
    entries = []
    # Agregar navegación
    entries.append("..")
    for it in sorted(items):
        full = os.path.join(path, it)
        if os.path.isdir(full):
            entries.append(it + "/")
        else:
            if allowed_exts is None:
                entries.append(it)
            else:
                _, ext = os.path.splitext(it.lower())
                if ext in allowed_exts:
                    entries.append(it)
    return entries

def clamp(n, a, b):
    return max(a, min(n, b))

# -----------------------------
# UI con curses
# -----------------------------
class SimpleMenu:
    def __init__(self, stdscr, title: str, options: List[str], preselect: int = 0):
        self.stdscr = stdscr
        self.title = title
        self.options = options
        self.index = clamp(preselect, 0, max(0, len(options)-1))

    def run(self) -> int:
        curses.curs_set(0)
        while True:
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            # título
            self.stdscr.addnstr(0, 0, self.title[:w-1], w-1, curses.A_BOLD)
            # instrucciones
            help_line = "↑/↓ mover, Enter seleccionar, q cancelar"
            self.stdscr.addnstr(1, 0, help_line[:w-1], w-1, curses.A_DIM)
            # ventana de opciones
            start_row = 3
            visible_rows = h - start_row - 1
            top = clamp(self.index - visible_rows//2, 0, max(0, len(self.options)-visible_rows))
            for i in range(visible_rows):
                idx = top + i
                if idx >= len(self.options):
                    break
                line = self.options[idx]
                attr = curses.A_REVERSE if idx == self.index else curses.A_NORMAL
                self.stdscr.addnstr(start_row+i, 0, line[:w-1], w-1, attr)
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord('q'), 27):
                return -1
            elif ch in (curses.KEY_UP, ord('k')):
                self.index = clamp(self.index-1, 0, len(self.options)-1)
            elif ch in (curses.KEY_DOWN, ord('j')):
                self.index = clamp(self.index+1, 0, len(self.options)-1)
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
            self.index = clamp(self.index, 0, max(0, len(self.entries)-1))
            self.stdscr.clear()
            h, w = self.stdscr.getmaxyx()
            self.stdscr.addnstr(0, 0, self.title[:w-1], w-1, curses.A_BOLD)
            path_line = f"Dir: {self.cwd}"
            self.stdscr.addnstr(1, 0, path_line[:w-1], w-1, curses.A_DIM)
            self.stdscr.addnstr(2, 0, "↑/↓ mover, Enter abrir/seleccionar, ← atrás, q cancelar"[:w-1], w-1, curses.A_DIM)
            start_row = 4
            visible_rows = h - start_row - 1
            top = clamp(self.index - visible_rows//2, 0, max(0, len(self.entries)-visible_rows))
            for i in range(visible_rows):
                idx = top + i
                if idx >= len(self.entries):
                    break
                e = self.entries[idx]
                attr = curses.A_REVERSE if idx == self.index else curses.A_NORMAL
                self.stdscr.addnstr(start_row+i, 0, e[:w-1], w-1, attr)
            self.stdscr.refresh()
            ch = self.stdscr.getch()
            if ch in (ord('q'), 27):
                return None
            elif ch in (curses.KEY_UP, ord('k')):
                self.index = clamp(self.index-1, 0, len(self.entries)-1)
            elif ch in (curses.KEY_DOWN, ord('j')):
                self.index = clamp(self.index+1, 0, len(self.entries)-1)
            elif ch in (curses.KEY_LEFT, 127, curses.KEY_BACKSPACE, 8):
                # subir un nivel
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
# Lógica FFMPEG
# -----------------------------
def build_ffmpeg_cmd(
    image_path: str,
    audio_path: str,
    out_path: str,
    resolution: str,  # "1280x720"
    acodec: str,      # "aac", "libmp3lame", "libopus"
    abr_kbps: int,    # e.g., 192
    framerate: int = 30
) -> List[str]:
    w, h = resolution.split("x")
    container = "mp4"
    vcodec = "libx264"
    extra_v = ["-tune", "stillimage", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-movflags", "+faststart"]
    # si Opus => usar VP9/WebM
    if acodec == "libopus":
        container = "webm"
        vcodec = "libvpx-vp9"
        # Para estático, CRF bajo/medio; bitrate variable OK
        extra_v = ["-pix_fmt", "yuv420p", "-crf", "32", "-b:v", "0"]

    if not out_path.lower().endswith("." + container):
        out_path = os.path.splitext(out_path)[0] + "." + container

    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-framerate", str(framerate),
        "-i", image_path,
        "-i", audio_path,
        "-c:v", vcodec,
        "-vf", vf,
        *extra_v,
        "-c:a", acodec,
        "-b:a", f"{abr_kbps}k",
        "-ar", "48000",  # 48 kHz recomendado
        "-shortest",
        # progreso en stdout
        "-progress", "pipe:1",
        "-nostats",
        out_path
    ]
    return cmd

def format_seconds(s: float) -> str:
    if s < 0: s = 0
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    else:
        return f"{m:02d}:{sec:02d}"

# -----------------------------
# Pantallas específicas
# -----------------------------
def show_message(stdscr, lines: List[str], footer: str = "Enter para continuar, q para cancelar") -> bool:
    curses.curs_set(0)
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        for i, ln in enumerate(lines[:h-2]):
            stdscr.addnstr(i, 0, ln[:w-1], w-1, curses.A_BOLD if i == 0 else curses.A_NORMAL)
        stdscr.addnstr(h-1, 0, footer[:w-1], w-1, curses.A_DIM)
        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord('q'), 27):
            return False
        if ch in (curses.KEY_ENTER, 10, 13):
            return True

def progress_screen(stdscr, cmd: List[str], total_duration: Optional[float]) -> int:
    """
    Ejecuta ffmpeg mostrando progreso y ETA.
    Devuelve el returncode de ffmpeg.
    """
    curses.curs_set(0)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    out_time = 0.0
    speed = 1.0
    last_refresh = 0.0
    rc = None

    # Bucle de lectura de progreso
    while True:
        line = proc.stdout.readline()
        if not line:
            # Puede que haya terminado; salir si el proceso acabó
            if proc.poll() is not None:
                rc = proc.returncode
                break
            else:
                time.sleep(0.05)
                continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if key == "out_time_ms":
            try:
                out_time = int(val)/1_000_000.0
            except:
                pass
        elif key == "speed":
            try:
                # speed suele ser "1.23x"
                if val.endswith("x"):
                    speed = float(val[:-1])
            except:
                pass

        now = time.time()
        if now - last_refresh >= 0.1:
            stdscr.clear()
            h, w = stdscr.getmaxyx()
            title = "Codificando con ffmpeg..."
            stdscr.addnstr(0, 0, title[:w-1], w-1, curses.A_BOLD)
            # barra y porcentaje
            if total_duration and total_duration > 0:
                pct = clamp(out_time / total_duration, 0.0, 1.0)
                filled = int(pct * (w-2))
                bar = "█"*filled + " "*(w-2-filled)
                stdscr.addnstr(2, 0, f"[{bar}]", w-1)
                stdscr.addnstr(3, 0, f"Progreso: {int(pct*100)}%", w-1)
                # ETA
                remaining = max(total_duration - out_time, 0.0)
                eta = remaining / (speed if speed > 0 else 1.0)
                stdscr.addnstr(4, 0, f"Tiempo restante estimado: {format_seconds(eta)}", w-1)
            else:
                stdscr.addnstr(2, 0, "Calculando duración...", w-1)

            stdscr.addnstr(6, 0, f"Velocidad: {speed:.2f}x", w-1, curses.A_DIM)
            stdscr.addnstr(h-1, 0, "Presiona q para cancelar (puede tardar unos segundos).", w-1, curses.A_DIM)
            stdscr.refresh()
            last_refresh = now

        # cancelar si q
        stdscr.nodelay(True)
        ch = stdscr.getch()
        if ch in (ord('q'), 27):
            try:
                proc.terminate()
                time.sleep(0.2)
                if proc.poll() is None:
                    proc.kill()
            except:
                pass
            return 130  # cancelado

    # Mostrar resultado
    stdscr.nodelay(False)
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    msg = "¡Completado!" if rc == 0 else f"ffmpeg terminó con código {rc}"
    stdscr.addnstr(0, 0, msg[:w-1], w-1, curses.A_BOLD if rc == 0 else curses.A_NORMAL)
    stdscr.addnstr(h-1, 0, "Enter para salir", w-1, curses.A_DIM)
    stdscr.refresh()
    while True:
        ch = stdscr.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            break
    return rc

# -----------------------------
# Flujo principal
# -----------------------------
def main(stdscr):
    curses.use_default_colors()
    start_dir = os.getcwd()

    # 1) Seleccionar IMAGEN
    img_picker = FilePicker(stdscr, start_dir, "Selecciona la IMAGEN (se usará como video estático)", IMG_EXTS)
    img_path = img_picker.run()
    if not img_path:
        return
    if not os.path.exists(img_path):
        show_message(stdscr, ["Error", "No se encontró la imagen."]); return

    # 2) Seleccionar AUDIO
    aud_picker = FilePicker(stdscr, os.path.dirname(img_path), "Selecciona el AUDIO (mp3/wav/etc.)", AUD_EXTS)
    aud_path = aud_picker.run()
    if not aud_path:
        return
    if not os.path.exists(aud_path):
        show_message(stdscr, ["Error", "No se encontró el audio."]); return

    # 3) Detectar bitrate del audio y sugerir
    opt_kbps = ffprobe_audio_bitrate_kbps(aud_path)
    dur_sec = ffprobe_duration_sec(aud_path)

    # Info de recomendaciones YouTube
    info_lines = [
        "Recomendaciones de YouTube (audio):",
        "- Codec: AAC-LC (recomendado).",
        "- Frecuencia de muestreo: 48 kHz.",
        "- Bitrate recomendado (estéreo): 128 kbps. Para 5.1: 384 kbps.",
        "",
        f"Bitrate detectado de tu archivo: {opt_kbps} kbps" if opt_kbps else "No se pudo detectar el bitrate de tu archivo.",
    ]
    ok = show_message(stdscr, info_lines)
    if not ok: return

    # 4) Elegir bitrate con preselección (siguiente superior al detectado)
    pre = 0
    pre_val = next_higher_bitrate(opt_kbps)
    br_opts = [f"{b} kbps" for b in AUDIO_BR_STEPS]
    if pre_val in AUDIO_BR_STEPS:
        pre = AUDIO_BR_STEPS.index(pre_val)
    br_menu = SimpleMenu(stdscr, "Elige el bitrate de audio (Enter para seleccionar)", br_opts, preselect=pre)
    br_idx = br_menu.run()
    if br_idx < 0: return
    sel_br = AUDIO_BR_STEPS[br_idx]

    # 5) Elegir codec/formato de audio
    ac_opts = [f"{c[0]} - {c[1]}" for c in AUDIO_CODECS]
    # por defecto AAC-LC
    ac_default = 0
    ac_menu = SimpleMenu(stdscr, "Elige el formato/codec de audio", ac_opts, preselect=ac_default)
    ac_idx = ac_menu.run()
    if ac_idx < 0: return
    acodec = AUDIO_CODECS[ac_idx][0]

    # 6) Elegir resolución de video
    vr_opts = [f"{r[1]} ({r[0]})" for r in VIDEO_RESOLUTIONS]
    # sugerir 1080p por defecto
    def_idx = 4  # 1080p
    vr_menu = SimpleMenu(stdscr, "Elige la resolución del video", vr_opts, preselect=def_idx)
    vr_idx = vr_menu.run()
    if vr_idx < 0: return
    resolution = VIDEO_RESOLUTIONS[vr_idx][0]

    # 7) Confirmación y salida final
    # Determinar contenedor por codec seleccionado
    container = "webm" if acodec == "libopus" else "mp4"
    suggested_out = os.path.join(os.path.dirname(aud_path), f"output_{int(time.time())}.{container}")
    summary = [
        "Resumen:",
        f"Imagen: {img_path}",
        f"Audio:  {aud_path}",
        f"Bitrate audio: {sel_br} kbps",
        f"Codec audio: {acodec}",
        f"Resolución: {resolution}",
        f"Salida: {suggested_out}",
        "",
        "Se usará video estático (imagen) con pad/escala para la resolución elegida.",
        "Enter para comenzar, q para cancelar."
    ]
    ok = show_message(stdscr, summary, footer="Enter para comenzar, q para cancelar")
    if not ok: return

    # 8) Construir comando ffmpeg
    cmd = build_ffmpeg_cmd(
        image_path=img_path,
        audio_path=aud_path,
        out_path=suggested_out,
        resolution=resolution,
        acodec=acodec,
        abr_kbps=sel_br,
        framerate=30
    )

    # 9) Progreso
    rc = progress_screen(stdscr, cmd, total_duration=dur_sec)

    # 10) Mensaje final con ruta de salida
    if rc == 0:
        show_message(stdscr, ["Hecho", f"Archivo creado: {suggested_out}"], footer="Enter para salir")
    elif rc == 130:
        show_message(stdscr, ["Cancelado", "Proceso detenido por el usuario."], footer="Enter para salir")
    else:
        show_message(stdscr, ["Error", f"ffmpeg terminó con código {rc}"], footer="Enter para salir")

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
