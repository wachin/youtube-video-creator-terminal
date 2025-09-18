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

        # Título
        self.stdscr.attron(curses.color_pair(COLOR_HEADER))
        self.stdscr.addstr(1, 2, f" {title} ", curses.A_BOLD)
        self.stdscr.attroff(curses.color_pair(COLOR_HEADER))

        # Ruta actual
        self.stdscr.addstr(2, 2, f"Directorio: {self.current_path}", curses.A_DIM)

        # Archivos
        start_y = 4
        for idx, f in enumerate(self.files):
            y = start_y + idx
            if y >= h - 2:
                break
            if idx == self.cursor:
                self.stdscr.attron(curses.color_pair(COLOR_HIGHLIGHT))
                self.stdscr.addstr(y, 2, f"> {f}")
                self.stdscr.attroff(curses.color_pair(COLOR_HIGHLIGHT))
            else:
                self.stdscr.addstr(y, 2, f"  {f}")

        self.stdscr.addstr(h - 1, 2, "↑↓: Navegar | ENTER: Seleccionar/Abrir | ESC: Cancelar")
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
        stdscr.attron(curses.color_pair(COLOR_HEADER))
        stdscr.addstr(1, 2, f" {title} ", curses.A_BOLD)
        stdscr.attroff(curses.color_pair(COLOR_HEADER))

        # Opciones
        start_y = 3
        for idx, opt in enumerate(options):
            y = start_y + idx
            if y >= h - 2:
                break
            if idx == cursor:
                stdscr.attron(curses.color_pair(COLOR_HIGHLIGHT))
                stdscr.addstr(y, 2, f"> {opt}")
                stdscr.attroff(curses.color_pair(COLOR_HIGHLIGHT))
            else:
                stdscr.addstr(y, 2, f"  {opt}")

        stdscr.addstr(h - 1, 2, "↑↓: Navegar | ENTER: Seleccionar | ESC: Cancelar")
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
        if total_duration is None:
            stdscr.addstr(2, 2, "⚠️ No se pudo obtener duración del audio. Progreso no disponible.", curses.A_BOLD)
            stdscr.refresh()
            time.sleep(2)

        stdscr.clear()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(2, 2, "🎬 Generando video con ffmpeg...", curses.A_BOLD)
        stdscr.addstr(4, 2, f"Audio: {os.path.basename(audio_path)}")
        if total_duration:
            stdscr.addstr(5, 2, f"Duración total: {format_time(total_duration)}")
        stdscr.addstr(7, 2, "Progreso:", curses.A_UNDERLINE)
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

                # Buscar tiempo actual en la línea
                match = time_regex.search(last_line)
                if match:
                    hours, minutes, seconds = map(float, match.groups())
                    current_time = hours * 3600 + minutes * 60 + seconds

                # Calcular progreso
                percent = 0
                if total_duration and total_duration > 0:
                    percent = min(100, int((current_time / total_duration) * 100))

                # Calcular tiempo restante estimado
                elapsed = time.time() - start_time
                eta = "--:--:--"
                if percent > 0 and total_duration:
                    estimated_total = elapsed / (percent / 100.0)
                    remaining = estimated_total - elapsed
                    eta = format_time(remaining) if remaining > 0 else "00:00:00"

                # Dibujar interfaz
                stdscr.clear()
                stdscr.addstr(2, 2, "🎬 Generando video con ffmpeg...", curses.A_BOLD)
                stdscr.addstr(4, 2, f"Audio: {os.path.basename(audio_path)}")
                if total_duration:
                    stdscr.addstr(5, 2, f"Duración total: {format_time(total_duration)}")

                # Barra de progreso
                bar_width = min(w - 20, 50)  # Máx 50 caracteres o ajustar a ancho
                filled = int(bar_width * percent / 100)
                bar = "[" + "=" * filled + ">" + " " * (bar_width - filled - 1) + "]"
                stdscr.addstr(7, 2, f"Progreso: {percent:3d}% {bar}")
                stdscr.addstr(8, 2, f"Tiempo: {format_time(current_time)} / {format_time(total_duration) if total_duration else '?'}")
                stdscr.addstr(9, 2, f"ETA: {eta} | Transcurrido: {format_time(elapsed)}")

                # Mostrar última línea técnica de ffmpeg (opcional)
                if last_line and "fps=" in last_line:
                    stdscr.addstr(11, 2, f"FFmpeg: {last_line[:w-4]}", curses.A_DIM)

                stdscr.addstr(h - 1, 2, "⏳ Procesando... (Presiona 'q' para salir sin cancelar)", curses.A_DIM)
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
            stdscr.addstr(2, 2, "✅ ¡Video generado con éxito!", curses.A_BOLD)
            stdscr.addstr(4, 2, f"Guardado como: {output_path}")
            if total_duration:
                stdscr.addstr(6, 2, f"Duración: {format_time(total_duration)}")
        else:
            stdscr.addstr(2, 2, "❌ Error al generar el video", curses.A_BOLD)
            stdscr.addstr(4, 2, f"Última línea: {last_line[:w-4]}")

        stdscr.addstr(h - 2, 2, "Presiona cualquier tecla para salir...")
        stdscr.refresh()
        stdscr.getch()

    except Exception as e:
        stdscr.clear()
        stdscr.addstr(2, 2, "⚠️ Excepción inesperada:", curses.A_BOLD)
        stdscr.addstr(4, 2, str(e)[:w-4])
        stdscr.addstr(6, 2, "Presiona cualquier tecla para salir...")
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
    resolution = select_from_list(stdscr, YOUTUBE_RESOLUTIONS, "Selecciona la resolución del video")
    if not resolution:
        return

    # Seleccionar formato de audio
    audio_format = select_from_list(stdscr, YOUTUBE_AUDIO_FORMATS, "Selecciona el formato de audio")
    if not audio_format:
        return

    # Generar nombre de salida
    base_name = Path(audio_path).stem
    output_path = f"{base_name}_youtube_{resolution.replace('x', 'p')}.{audio_format}.mp4"

    # Confirmar
    stdscr.clear()
    stdscr.addstr(2, 2, "¿Deseas generar el video con estas opciones?", curses.A_BOLD)
    stdscr.addstr(4, 4, f"Imagen: {image_path}")
    stdscr.addstr(5, 4, f"Audio: {audio_path}")
    stdscr.addstr(6, 4, f"Resolución: {resolution}")
    stdscr.addstr(7, 4, f"Audio codec: {audio_format}")
    stdscr.addstr(8, 4, f"Salida: {output_path}")
    stdscr.addstr(10, 2, "Presiona ENTER para confirmar, ESC para cancelar.")
    stdscr.refresh()

    key = stdscr.getch()
    if key not in [10, 13]:
        return

    # Ejecutar ffmpeg
    run_ffmpeg(image_path, audio_path, resolution, audio_format, output_path)


if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        print("❌ Error: ffmpeg no está instalado. Instálalo con:")
        print("   sudo apt install ffmpeg   # Ubuntu/Debian")
        print("   sudo dnf install ffmpeg   # Fedora")
        sys.exit(1)

    try:
        import shutil
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("\n👋 Saliendo...")
