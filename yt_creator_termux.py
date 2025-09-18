#!/usr/bin/env python3

import curses
import os
import subprocess
import sys
import shutil
import re
import time
from pathlib import Path

# Resoluciones recomendadas por YouTube
YOUTUBE_RESOLUTIONS = [
    "426x240",     # 240p
    "640x360",     # 360p
    "854x480",     # 480p
    "1280x720",    # 720p HD
    "1920x1080",   # 1080p Full HD
    "2560x1440",   # 1440p QHD
    "3840x2160",   # 2160p 4K UHD
]

# Formatos de audio recomendados por YouTube
YOUTUBE_AUDIO_FORMATS = [
    "aac",         # AAC-LC (recomendado)
    "mp3",         # MP3 (compatible, pero no óptimo)
    "vorbis",      # Vorbis (para WebM)
    "opus",        # Opus (alta eficiencia, para WebM/MP4)
]

# Colores para curses
COLOR_HEADER = 1
COLOR_HIGHLIGHT = 2
COLOR_NORMAL = 3


def truncate(text, width):
    """Trunca texto si excede el ancho, añadiendo '...' al final."""
    if len(text) <= width:
        return text
    if width < 4:
        return ""
    return text[:width - 3] + "..."


class FileSelector:
    def __init__(self, stdscr, start_path=".", extensions=None):
        self.stdscr = stdscr
        self.current_path = Path(start_path).resolve()
        self.cursor = 0
        self.extensions = [ext.lower() for ext in extensions] if extensions else []
        self.files = []
        self.update_files()

    def update_files(self):
        try:
            if self.extensions:
                self.files = [".."] + sorted([
                    f.name for f in self.current_path.iterdir()
                    if f.is_dir() or (f.is_file() and f.suffix.lower() in self.extensions)
                ])
            else:
                self.files = [".."] + sorted([
                    f.name for f in self.current_path.iterdir()
                ])
        except PermissionError:
            self.files = [".."]
        self.cursor = min(self.cursor, len(self.files) - 1)

    def navigate(self, direction):
        self.cursor = max(0, min(self.cursor + direction, len(self.files) - 1))

    def enter(self):
        selected = self.files[self.cursor]
        if selected == "..":
            self.current_path = self.current_path.parent
        else:
            next_path = self.current_path / selected
            if next_path.is_dir():
                self.current_path = next_path
            else:
                return str(next_path.resolve())
        self.cursor = 0
        self.update_files()
        return None

    def draw(self, title="Selecciona un archivo"):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()

        # Título (ajustado)
        title = truncate(f" {title} ", w - 4)
        self.stdscr.attron(curses.color_pair(COLOR_HEADER))
        self.stdscr.addnstr(1, 2, title, w - 4, curses.A_BOLD)
        self.stdscr.attroff(curses.color_pair(COLOR_HEADER))

        # Ruta actual (truncada)
        path_str = truncate(f"Dir: {self.current_path}", w - 4)
        self.stdscr.addnstr(2, 2, path_str, w - 4, curses.A_DIM)

        # Archivos
        start_y = 4
        for idx, f in enumerate(self.files):
            y = start_y + idx
            if y >= h - 2:
                break
            display = truncate(f"{'>' if idx == self.cursor else ' '} {f}", w - 4)
            if idx == self.cursor:
                self.stdscr.attron(curses.color_pair(COLOR_HIGHLIGHT))
                self.stdscr.addnstr(y, 2, display, w - 4)
                self.stdscr.attroff(curses.color_pair(COLOR_HIGHLIGHT))
            else:
                self.stdscr.addnstr(y, 2, display, w - 4)

        # Instrucciones (ajustadas)
        instr = "↑↓: Navegar | ENTER: Sel | ESC: Cancelar"
        self.stdscr.addnstr(h - 1, 2, instr, w - 4)
        self.stdscr.refresh()

    def run(self):
        while True:
            self.draw()
            key = self.stdscr.getch()
            if key == curses.KEY_UP:
                self.navigate(-1)
            elif key == curses.KEY_DOWN:
                self.navigate(1)
            elif key == curses.KEY_ENTER or key in [10, 13]:
                result = self.enter()
                if result:
                    return result
            elif key == 27:  # ESC
                return None


def select_from_list(stdscr, options, title="Selecciona una opción"):
    cursor = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        # Título
        title_display = truncate(f" {title} ", w - 4)
        stdscr.attron(curses.color_pair(COLOR_HEADER))
        stdscr.addnstr(1, 2, title_display, w - 4, curses.A_BOLD)
        stdscr.attroff(curses.color_pair(COLOR_HEADER))

        # Opciones
        start_y = 3
        for idx, opt in enumerate(options):
            y = start_y + idx
            if y >= h - 2:
                break
            display = truncate(f"{'>' if idx == cursor else ' '} {opt}", w - 4)
            if idx == cursor:
                stdscr.attron(curses.color_pair(COLOR_HIGHLIGHT))
                stdscr.addnstr(y, 2, display, w - 4)
                stdscr.attroff(curses.color_pair(COLOR_HIGHLIGHT))
            else:
                stdscr.addnstr(y, 2, display, w - 4)

        instr = "↑↓: Navegar | ENTER: Sel | ESC: Cancelar"
        stdscr.addnstr(h - 1, 2, instr, w - 4)
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_DOWN:
            cursor = min(len(options) - 1, cursor + 1)
        elif key == curses.KEY_ENTER or key in [10, 13]:
            return options[cursor]
        elif key == 27:  # ESC
            return None


def get_audio_duration(audio_path):
    """Obtiene la duración del audio en segundos usando ffprobe."""
    try:
        result = subprocess.run([
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ], capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return None


def format_time(seconds):
    """Convierte segundos a formato HH:MM:SS."""
    if seconds is None:
        return "--:--:--"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def run_ffmpeg(image_path, audio_path, resolution, audio_format, output_path):
    w, h = resolution.split('x')
    audio_codec_map = {
        "aac": "aac",
        "mp3": "libmp3lame",
        "vorbis": "libvorbis",
        "opus": "libopus",
    }
    audio_codec = audio_codec_map.get(audio_format, "aac")

    cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", audio_codec,
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]

    stdscr = curses.initscr()
    try:
        # Obtener duración del audio
        total_duration = get_audio_duration(audio_path)

        stdscr.clear()
        h, w = stdscr.getmaxyx()
        stdscr.addnstr(1, 1, "🎬 Generando video...", w - 2, curses.A_BOLD)

        # Mostrar nombre de audio acortado
        audio_name = truncate(os.path.basename(audio_path), w - 10)
        stdscr.addnstr(2, 1, f"🎵 {audio_name}", w - 2)

        if total_duration:
            stdscr.addnstr(3, 1, f"⏱️  Total: {format_time(total_duration)}", w - 2)

        stdscr.addnstr(4, 1, "▬" * (w - 2), w - 2)  # Línea separadora
        stdscr.refresh()

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Regex para extraer tiempo de ffmpeg: "time=00:00:12.34"
        time_regex = re.compile(r"time=(\d+):(\d+):(\d+\.?\d*)")

        start_time = time.time()
        last_line = ""
        current_time = 0.0

        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                last_line = output.strip()

                # Buscar tiempo actual
                match = time_regex.search(last_line)
                if match:
                    hours, minutes, seconds = map(float, match.groups())
                    current_time = hours * 3600 + minutes * 60 + seconds

                # Calcular progreso
                percent = 0
                if total_duration and total_duration > 0:
                    percent = min(100, int((current_time / total_duration) * 100))

                # Calcular ETA
                elapsed = time.time() - start_time
                eta = "--:--:--"
                if percent > 0 and total_duration:
                    estimated_total = elapsed / (percent / 100.0)
                    remaining = estimated_total - elapsed
                    eta = format_time(remaining) if remaining > 0 else "00:00:00"

                # Redibujar interfaz
                stdscr.clear()

                # Encabezado compacto
                stdscr.addnstr(0, 1, f"🎬 {percent:3d}% | ETA: {eta}", w - 2, curses.A_BOLD)

                # Barra de progreso adaptativa
                bar_width = max(10, w - 10)  # Mínimo 10 caracteres
                filled = int(bar_width * percent / 100)
                bar = "█" * filled + "░" * (bar_width - filled)
                stdscr.addnstr(1, 1, bar, w - 2)

                # Tiempos
                stdscr.addnstr(2, 1, f"▶ {format_time(current_time)} / {format_time(total_duration) if total_duration else '?'}", w - 2)
                stdscr.addnstr(3, 1, f"⏱️ Transcurrido: {format_time(elapsed)}", w - 2)

                # FPS/Bitrate (si está disponible)
                if "fps=" in last_line and "bitrate=" in last_line:
                    try:
                        fps_part = last_line.split("fps=")[1].split()[0]
                        br_part = last_line.split("bitrate=")[1].split()[0]
                        status = f"📊 {fps_part}fps | {br_part}"
                        stdscr.addnstr(4, 1, truncate(status, w - 2), w - 2)
                    except:
                        pass

                stdscr.addnstr(h - 1, 1, "[q] Salir (no cancela)", w - 2, curses.A_DIM)
                stdscr.refresh()

                # Permitir salir con 'q'
                stdscr.nodelay(True)
                key = stdscr.getch()
                if key == ord('q'):
                    stdscr.nodelay(False)
                    break
                stdscr.nodelay(False)

        # Resultado final
        stdscr.clear()
        return_code = process.poll()
        if return_code == 0:
            stdscr.addnstr(1, 1, "✅ ¡ÉXITO!", w - 2, curses.A_BOLD)
            stdscr.addnstr(3, 1, truncate(f"📁 {output_path}", w - 2), w - 2)
            if total_duration:
                stdscr.addnstr(4, 1, f"⏱️ Duración: {format_time(total_duration)}", w - 2)
        else:
            stdscr.addnstr(1, 1, "❌ ERROR", w - 2, curses.A_BOLD)
            stdscr.addnstr(3, 1, truncate(last_line, w - 2), w - 2)

        stdscr.addnstr(h - 1, 1, "Presiona cualquier tecla...", w - 2)
        stdscr.refresh()
        stdscr.getch()

    except Exception as e:
        stdscr.clear()
        stdscr.addnstr(1, 1, "⚠️ ERROR INTERNO", w - 2, curses.A_BOLD)
        stdscr.addnstr(3, 1, truncate(str(e), w - 2), w - 2)
        stdscr.addnstr(h - 1, 1, "Presiona cualquier tecla...", w - 2)
        stdscr.refresh()
        stdscr.getch()
    finally:
        curses.endwin()


def main(stdscr):
    # Inicializar colores
    curses.start_color()
    curses.init_pair(COLOR_HEADER, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(COLOR_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(COLOR_NORMAL, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.curs_set(0)
    stdscr.keypad(True)

    # Seleccionar imagen
    image_selector = FileSelector(stdscr, extensions=[".jpg", ".jpeg", ".png", ".bmp", ".gif"])
    image_path = image_selector.run()
    if not image_path:
        return

    # Seleccionar audio
    audio_selector = FileSelector(stdscr, extensions=[".mp3", ".wav", ".ogg", ".flac", ".m4a"])
    audio_path = audio_selector.run()
    if not audio_path:
        return

    # Seleccionar resolución
    resolution = select_from_list(stdscr, YOUTUBE_RESOLUTIONS, "Resolución")
    if not resolution:
        return

    # Seleccionar formato de audio
    audio_format = select_from_list(stdscr, YOUTUBE_AUDIO_FORMATS, "Formato de audio")
    if not audio_format:
        return

    # Generar nombre de salida
    base_name = Path(audio_path).stem
    # Sanitizar nombre para evitar problemas en sistemas con espacios o caracteres raros
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', base_name)
    output_path = f"{safe_name}_yt_{resolution.replace('x', 'p')}.{audio_format}.mp4"

    # Confirmar
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    stdscr.addnstr(1, 1, "¿Confirmar creación?", w - 2, curses.A_BOLD)
    stdscr.addnstr(3, 1, truncate(f"🖼️  {os.path.basename(image_path)}", w - 2), w - 2)
    stdscr.addnstr(4, 1, truncate(f"🎵 {os.path.basename(audio_path)}", w - 2), w - 2)
    stdscr.addnstr(5, 1, f"📺 {resolution} | 🔊 {audio_format}", w - 2)
    stdscr.addnstr(6, 1, truncate(f"💾 {output_path}", w - 2), w - 2)
    stdscr.addnstr(h - 1, 1, "ENTER: Sí | ESC: No", w - 2)
    stdscr.refresh()

    key = stdscr.getch()
    if key not in [10, 13]:
        return

    # Ejecutar ffmpeg
    run_ffmpeg(image_path, audio_path, resolution, audio_format, output_path)


if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg no encontrado. Instálalo:")
        print("Termux: pkg install ffmpeg")
        print("Linux: sudo apt install ffmpeg")
        sys.exit(1)
    if not shutil.which("ffprobe"):
        print("❌ ffprobe no encontrado (viene con ffmpeg).")
        sys.exit(1)

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
