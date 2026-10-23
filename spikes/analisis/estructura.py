"""Estructura: segmentación por autosimilitud con librosa sobre una grilla de beats (beat_this).

Dos variantes:
- `novedad`: matriz de autosimilitud (chroma + MFCC por beat), kernel tablero de ajedrez, picos de novedad.
- `agglomerative`: clustering aglomerativo con restricción temporal (librosa.segment.agglomerative), k = compases/8.

Los límites se ajustan al downbeat más cercano. No hay límites de referencia con tiempos (Cifra Club no los trae),
así que se miden proxies: cantidad de secciones, límites propios sobre downbeat y acuerdo entre variantes y
con los cambios de progresión de BTC (F-measure con ventana de 3 s, mir_eval).
"""

import json
import time
from pathlib import Path

import librosa
import mir_eval
import numpy as np
import scipy.ndimage
from acordes_comun import leer_linea
from scipy.signal import find_peaks
from songs import SONGS, wav_path

BEATS = Path(__file__).parent / "resultados" / "beats" / "beat_this"
SALIDA = Path(__file__).parent / "resultados" / "estructura.json"
VENTANA = 3.0
MIN_COMPASES = 4  # separación mínima entre límites


def caracteristicas(ruta: Path, beats: np.ndarray) -> np.ndarray:
    y, sr = librosa.load(str(ruta), sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    frames = librosa.time_to_frames(beats, sr=sr)
    sync = lambda m: librosa.util.sync(m, frames, aggregate=np.median)
    c, m = sync(chroma), sync(librosa.util.normalize(mfcc[1:], axis=1))
    return np.vstack(
        [librosa.util.normalize(c, axis=0), 0.5 * librosa.util.normalize(m, axis=0)]
    )


def novedad(feat: np.ndarray, beats: np.ndarray, por_compas: int) -> np.ndarray:
    ssm = librosa.segment.recurrence_matrix(feat, mode="affinity", sym=True, width=3)
    ssm = scipy.ndimage.uniform_filter(ssm, size=(3, 3))
    k = 8 * por_compas
    kernel = np.sign(
        np.outer(np.r_[-np.ones(k), np.ones(k)], np.r_[-np.ones(k), np.ones(k)])
    )
    n = ssm.shape[0]
    pad = np.pad(ssm, k, mode="edge")
    curva = np.array(
        [(pad[i : i + 2 * k, i : i + 2 * k] * kernel).sum() for i in range(n)]
    )
    picos, _ = find_peaks(
        curva, distance=MIN_COMPASES * por_compas, prominence=curva.std() * 0.5
    )
    return beats[picos]


def aglomerativa(feat: np.ndarray, beats: np.ndarray, por_compas: int) -> np.ndarray:
    k = max(3, feat.shape[1] // (8 * por_compas))
    idx = librosa.segment.agglomerative(feat, k)
    return beats[idx[1:]]


def ajustar_a_downbeats(limites: np.ndarray, downbeats: np.ndarray) -> np.ndarray:
    if len(limites) == 0:
        return limites
    return np.unique(
        downbeats[np.abs(downbeats[None, :] - limites[:, None]).argmin(axis=1)]
    )


def intervalos(limites: np.ndarray, duracion: float) -> np.ndarray:
    pts = np.r_[0.0, limites[(limites > 0) & (limites < duracion)], duracion]
    return np.c_[pts[:-1], pts[1:]]


def acuerdo(a: np.ndarray, b: np.ndarray, duracion: float) -> float:
    if len(a) == 0 or len(b) == 0:
        return 0.0
    f = mir_eval.segment.detection(
        intervalos(a, duracion), intervalos(b, duracion), window=VENTANA, trim=True
    )[2]
    return round(float(f), 3)


def limites_de_progresion(slug: str, duracion: float) -> np.ndarray:
    """Cambios de 'ciclo armónico': instantes donde la ventana de 8 acordes siguiente difiere de la anterior."""
    tramos = [
        t
        for t in leer_linea("btc_voca", slug)["tramos"]
        if t[1] - t[0] >= 0.4 and t[2] not in ("N", "X")
    ]
    etiquetas = [t[2] for t in tramos]
    puntos = []
    for i in range(8, len(tramos) - 8):
        antes, despues = set(etiquetas[i - 8 : i]), set(etiquetas[i : i + 8])
        if len(antes ^ despues) >= 3:
            puntos.append(tramos[i][0])
    pts = np.array(puntos)
    if len(pts) == 0:
        return pts
    return pts[np.r_[True, np.diff(pts) > 12.0]]


if __name__ == "__main__":
    salida = {}
    for slug in SONGS:
        datos = json.loads((BEATS / f"{slug}.json").read_text())
        beats, downbeats = np.array(datos["beats"]), np.array(datos["downbeats"])
        por_compas = 4
        duracion = librosa.get_duration(path=str(wav_path(slug)))
        t0 = time.perf_counter()
        feat = caracteristicas(wav_path(slug), beats)
        res = {}
        for nombre, f in (("novedad", novedad), ("agglomerative", aglomerativa)):
            res[nombre] = ajustar_a_downbeats(f(feat, beats, por_compas), downbeats)
        seg = time.perf_counter() - t0
        prog = limites_de_progresion(slug, duracion)
        salida[slug] = {
            "duracion": round(duracion, 1),
            "segundos": round(seg, 1),
            **{
                n: {
                    "n_secciones": len(r) + 1,
                    "limites": [round(float(x), 1) for x in r],
                    "acuerdo_con_progresion_btc": acuerdo(r, prog, duracion),
                }
                for n, r in res.items()
            },
            "acuerdo_entre_variantes": acuerdo(
                res["novedad"], res["agglomerative"], duracion
            ),
            "limites_progresion_btc": [round(float(x), 1) for x in prog],
        }
        print(slug, json.dumps(salida[slug]))
    SALIDA.write_text(json.dumps(salida, indent=2))
