"""Mide basic-pitch y pYIN sobre los riffs sintéticos y barre los umbrales de basic-pitch.

Uso: python medir.py [--barrido]    (escribe resultados/medicion.json y resultados/barrido.json)
"""

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

from metricas import evaluar, leer_referencia
from sintetizar import SALIDA, generar
from transcribir import basic_pitch_notas, pyin_notas

RESULTADOS = Path(__file__).parent / "resultados"
GRILLA = {
    "onset_threshold": [0.3, 0.5, 0.7],
    "frame_threshold": [0.2, 0.3, 0.4],
    "minimum_note_length": [58.0, 80.0, 127.7],  # ms
}


def casos() -> list[tuple[str, Path, np.ndarray]]:
    generar()
    return [
        (wav.stem, wav, leer_referencia(wav.with_suffix(".json")))
        for wav in sorted(SALIDA.glob("*.wav"))
    ]


def promedio(filas: list[dict], clave: str) -> float:
    return float(np.mean([f[clave] for f in filas]))


def medir_candidatos(lista) -> dict:
    basic_pitch_notas(lista[0][1])  # calentamiento: carga del modelo fuera del cronómetro
    resultado: dict[str, dict] = {"basic_pitch": {}, "pyin": {}}
    for nombre, wav, ref in lista:
        for cand, fn in (("basic_pitch", basic_pitch_notas), ("pyin", pyin_notas)):
            t0 = time.perf_counter()
            est = fn(wav)
            seg = time.perf_counter() - t0
            m = evaluar(ref, est)
            m.update(segundos=seg, notas_ref=len(ref), notas_est=len(est))
            resultado[cand][nombre] = m
            print(f"{cand:12s} {nombre:26s} F1={m['f1']:.2f} F1off={m['f1_off']:.2f} {seg:.1f}s")
    return resultado


def barrido(lista) -> list[dict]:
    filas = []
    for ot, ft, mn in itertools.product(*GRILLA.values()):
        por_caso = [
            evaluar(
                ref,
                basic_pitch_notas(
                    wav, onset_threshold=ot, frame_threshold=ft, minimum_note_length=mn
                ),
            )
            for _, wav, ref in lista
        ]
        fila = {
            "onset_threshold": ot,
            "frame_threshold": ft,
            "minimum_note_length": mn,
            "f1": promedio(por_caso, "f1"),
            "f1_off": promedio(por_caso, "f1_off"),
        }
        filas.append(fila)
        print(fila)
    return sorted(filas, key=lambda f: -f["f1"])


if __name__ == "__main__":
    RESULTADOS.mkdir(exist_ok=True)
    lista = casos()
    if "--barrido" in sys.argv:
        salida = barrido(lista)
        (RESULTADOS / "barrido.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")
    else:
        salida = medir_candidatos(lista)
        (RESULTADOS / "medicion.json").write_text(json.dumps(salida, indent=1), encoding="utf-8")
