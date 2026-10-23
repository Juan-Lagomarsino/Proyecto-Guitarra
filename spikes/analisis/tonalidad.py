"""Tonalidad: Krumhansl-Schmuckler sobre chroma de librosa y sobre el histograma de acordes del ganador.

Compara con la tonalidad de Cifra Club (`tonalidad`; todas las fixtures tienen capo 0).
Resultado: exacta, relativa (mayor <-> menor relativo) o distinta.
"""

import json
import time
from pathlib import Path

import librosa
import numpy as np
from acordes_comun import leer_linea
from evaluar_acordes import FIXTURES, normalizar
from songs import SONGS, wav_path

NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Perfiles de Krumhansl-Kessler (1982).
MAYOR = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MENOR = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)


def mejor_tonalidad(histograma: np.ndarray) -> tuple[int, bool]:
    """(tónica, es_menor) con mayor correlación contra los perfiles rotados."""
    candidatos = []
    for tonica in range(12):
        for es_menor, perfil in ((False, MAYOR), (True, MENOR)):
            r = np.corrcoef(histograma, np.roll(perfil, tonica))[0, 1]
            candidatos.append((r, tonica, es_menor))
    _, tonica, es_menor = max(candidatos)
    return tonica, es_menor


def ks_chroma(ruta: Path) -> tuple[int, bool]:
    y, sr = librosa.load(str(ruta), sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    return mejor_tonalidad(chroma.mean(axis=1))


def ks_acordes(herramienta: str, slug: str) -> tuple[int, bool]:
    """Histograma de pitch classes de las tríadas, ponderado por duración."""
    h = np.zeros(12)
    for ini, fin, etiqueta in leer_linea(herramienta, slug)["tramos"]:
        a = normalizar(etiqueta)
        if a is None:
            continue
        raiz, menor = a
        for i in (0, 3 if menor else 4, 7):
            h[(raiz + i) % 12] += fin - ini
    return mejor_tonalidad(h)


def etiqueta(clave: tuple[int, bool]) -> str:
    return NOTAS[clave[0]] + ("m" if clave[1] else "")


def comparar(detectada: tuple[int, bool], referencia: str | None) -> str:
    if not referencia:
        return "sin referencia"
    ref = normalizar(referencia)
    if ref == detectada:
        return "exacta"
    relativa = ((detectada[0] + (3 if detectada[1] else -3)) % 12, not detectada[1])
    return "relativa" if ref == relativa else "distinta"


if __name__ == "__main__":
    salida = {}
    for slug in SONGS:
        ficha = FIXTURES / f"{slug}.json"
        referencia = (
            json.loads(ficha.read_text(encoding="utf-8"))["tonalidad"]
            if ficha.exists()
            else None
        )
        t0 = time.perf_counter()
        claves = {"ks_chroma": ks_chroma(wav_path(slug))}
        seg = time.perf_counter() - t0
        for h in ("btc_voca", "plantillas"):
            claves[f"ks_{h}"] = ks_acordes(h, slug)
        salida[slug] = {
            "referencia_cifraclub": referencia,
            "segundos_ks_chroma": round(seg, 1),
            **{
                k: {"clave": etiqueta(v), "vs_referencia": comparar(v, referencia)}
                for k, v in claves.items()
            },
        }
        print(slug, json.dumps(salida[slug], ensure_ascii=False))
    (Path(__file__).parent / "resultados" / "tonalidad.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8"
    )
