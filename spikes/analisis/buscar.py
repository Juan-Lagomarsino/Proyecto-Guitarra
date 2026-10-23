"""Busca candidatos en YouTube (solo metadatos) para elegir la versión de estudio."""

import sys

from yt_dlp import YoutubeDL

QUERIES = sys.argv[1:]
OPTS = {"quiet": True, "extract_flat": True, "skip_download": True}

with YoutubeDL(OPTS) as ydl:
    for q in QUERIES:
        print("==", q)
        info = ydl.extract_info(f"ytsearch6:{q}", download=False)
        for e in info["entries"]:
            print(e["id"], e.get("duration"), e["title"], "|", e.get("channel"))
