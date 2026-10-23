"""Baja el audio de las 5 canciones a la caché local (nunca al repo) como WAV 48 kHz."""

import os
from pathlib import Path

from songs import CACHE, SONGS, wav_path
from yt_dlp import YoutubeDL

FFMPEG_DIR = os.environ.get("FFMPEG_DIR")


def descargar(slug: str, youtube_id: str) -> None:
    destino = wav_path(slug)
    if destino.exists():
        return
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(CACHE / f"{slug}.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "postprocessor_args": {"extractaudio": ["-ar", "48000"]},
        "quiet": True,
        "socket_timeout": 30,
    }
    if FFMPEG_DIR:
        opts["ffmpeg_location"] = FFMPEG_DIR
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}")
    print(slug, youtube_id, info.get("duration"), info.get("title"))


if __name__ == "__main__":
    Path(CACHE).mkdir(parents=True, exist_ok=True)
    for slug, datos in SONGS.items():
        descargar(slug, datos["youtube_id"])
