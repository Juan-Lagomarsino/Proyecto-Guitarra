"""Salida común de los reconocedores de acordes: una línea de tiempo [(inicio, fin, etiqueta)] por canción."""

import json
from pathlib import Path

SALIDA = Path(__file__).parent / "resultados" / "acordes"


def guardar_linea(herramienta: str, slug: str, tramos: list, segundos: float) -> None:
    destino = SALIDA / herramienta
    destino.mkdir(parents=True, exist_ok=True)
    datos = {
        "segundos": segundos,
        "tramos": [[round(a, 3), round(b, 3), c] for a, b, c in tramos],
    }
    (destino / f"{slug}.json").write_text(json.dumps(datos), encoding="utf-8")


def leer_linea(herramienta: str, slug: str) -> dict:
    return json.loads(
        (SALIDA / herramienta / f"{slug}.json").read_text(encoding="utf-8")
    )
