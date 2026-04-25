# YouTube Video Creator (de Terminal)

![Python](https://img.shields.io/badge/Python-3.x-blue)
![FFmpeg](https://img.shields.io/badge/FFmpeg-required-brightgreen)
![Interfaz](https://img.shields.io/badge/UI-Terminal%20(curses)-orange)
![Salida](https://img.shields.io/badge/Output-MP4%20%7C%20WebM-red)

Crea un video sencillo para YouTube a partir de una sola imagen y un archivo de audio directamente desde la terminal.

Este proyecto ofrece una interfaz basada en `curses` que te permite elegir una imagen, seleccionar una pista de audio, definir opciones de codificación y renderizar un video final con `ffmpeg`.

## Características

- Convierte una imagen estática y un archivo de audio en un video.
- Permite navegar archivos desde la terminal con un selector interactivo.
- Detecta el bitrate del audio de origen con `ffprobe`.
- Permite elegir el bitrate de audio, el códec y la resolución objetivo del video.
- Genera salida en `MP4` para AAC/MP3 o en `WebM` para Opus.
- Muestra el progreso de codificación, la velocidad y el tiempo restante estimado.

## Requisitos

- Python 3
- `ffmpeg`
- `ffprobe`
- Un entorno de terminal con soporte para `curses` en Python

## Formatos de Entrada Soportados

### Imágenes

`jpg`, `jpeg`, `png`, `bmp`, `webp`

### Audio

`mp3`, `wav`, `m4a`, `aac`, `flac`, `ogg`, `opus`, `wma`

## Cómo Funciona

1. Selecciona una imagen estática.
2. Selecciona un archivo de audio.
3. Revisa las recomendaciones orientadas a YouTube para el audio.
4. Elige el bitrate de audio.
5. Elige el códec de audio.
6. Elige la resolución del video.
7. Confirma el resumen e inicia la codificación.

Después, el script construye un comando de `ffmpeg` que repite la imagen, ajusta la duración de salida a la del audio y exporta un archivo de video listo para subir.

## Uso

Ejecuta:

```bash
python3 yt_creator_ES.py
```

## Controles

- `Up` / `Down`: mover entre opciones
- `Enter`: seleccionar
- `Left` / `Backspace`: subir un nivel en el selector de archivos
- `q` o `Esc`: cancelar

## Salida

- Contenedor por defecto: `MP4`
- Si se selecciona `libopus`, la salida cambia a `WebM`
- Formato del nombre de archivo de salida:

```text
output_<timestamp>.mp4
output_<timestamp>.webm
```

El archivo generado se guarda en el mismo directorio que el audio seleccionado.

## Notas

- El script está enfocado únicamente en la generación local de video.
- No sube videos a YouTube.
- El audio se codifica a `48 kHz`, lo cual coincide con recomendaciones habituales de YouTube.
- Para salidas que no usan Opus, el video se codifica con `libx264`.

## Archivo del Proyecto

- `yt_creator_ES.py`: aplicacion principal de terminal
