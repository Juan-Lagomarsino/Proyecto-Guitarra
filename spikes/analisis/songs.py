"""Las 5 canciones del spike: fuente de audio y BPM de referencia."""

from pathlib import Path

CACHE = Path("C:/Users/juanp/GuitarApp/cache/spike")

SONGS = {
    "flaca": {
        "title": "Flaca",
        "artist": "Andrés Calamaro",
        "youtube_id": "UCF9oHXhDMU",
        "bpm_ref": 109,
        "cifraclub": "andres-calamaro/flaca",
    },
    "de-musica-ligera": {
        "title": "De música ligera",
        "artist": "Soda Stereo",
        "youtube_id": "T_FkEw27XJ0",
        "bpm_ref": 124,
        "cifraclub": "soda-stereo/de-musica-ligera",
    },
    "boys-dont-cry": {
        "title": "Boys Don't Cry",
        "artist": "The Cure",
        "youtube_id": "9GkVhgIeGJQ",
        "bpm_ref": 169,
        "cifraclub": "the-cure/boys-dont-cry",
    },
    "cerca-del-fuego": {
        "title": "Cerca del fuego",
        "artist": "La Barranca",
        "youtube_id": "-HlcQsAsJbg",
        "bpm_ref": 115,
        "cifraclub": "la-barranca/cerca-del-fuego",
    },
    "no-voy-en-tren": {
        "title": "No voy en tren",
        "artist": "Charly García",
        "youtube_id": "P3L10KNMptw",
        "bpm_ref": 124,
        "cifraclub": "charly-garcia/no-voy-en-tren",
    },
}


def wav_path(slug: str) -> Path:
    return CACHE / f"{slug}.wav"
