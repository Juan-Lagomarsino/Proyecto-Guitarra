"""Muestra el ciclo de cada sección de la referencia y el inicio de la progresión detectada (revisión a ojo)."""

import sys

from acordes_comun import leer_linea
from evaluar_acordes import (
    cargar_referencia,
    ciclo_minimo,
    limpiar_detectado,
    sin_repetidos,
)

NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def texto(acordes) -> str:
    return " ".join(NOTAS[r] + ("m" if m else "") for r, m in acordes)


herramienta, slug = sys.argv[1], sys.argv[2]
for nombre, acordes in cargar_referencia(slug)["secciones"]:
    print(f"{nombre:16s} {texto(ciclo_minimo(sin_repetidos(acordes)))}")
print(
    "detectado:", texto(limpiar_detectado(leer_linea(herramienta, slug)["tramos"])[:60])
)
