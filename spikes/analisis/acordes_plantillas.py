"""Línea base de acordes: plantillas de tríadas mayores/menores sobre chroma CQT de librosa + Viterbi.

Uso: python acordes_plantillas.py
"""

import time

import librosa
import numpy as np
from acordes_comun import guardar_linea
from songs import SONGS, wav_path

NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SR, HOP = 22050, 4096


def plantillas() -> tuple[np.ndarray, list[str]]:
    filas, etiquetas = [], []
    for raiz in range(12):
        for nombre, intervalos in (("", (0, 4, 7)), (":min", (0, 3, 7))):
            v = np.zeros(12)
            v[[(raiz + i) % 12 for i in intervalos]] = 1.0
            filas.append(v / np.linalg.norm(v))
            etiquetas.append(NOTAS[raiz] + nombre)
    return np.array(filas), etiquetas


def reconocer(ruta) -> list[tuple[float, float, str]]:
    y, sr = librosa.load(str(ruta), sr=SR, mono=True)
    y = librosa.effects.harmonic(y, margin=4)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=HOP)
    chroma = librosa.util.normalize(chroma, norm=2, axis=0)
    chroma = np.apply_along_axis(
        lambda f: np.convolve(f, np.ones(3) / 3, mode="same"), 1, chroma
    )
    plant, etiquetas = plantillas()
    puntaje = plant @ chroma
    prob = librosa.util.normalize(np.exp(8 * puntaje), norm=1, axis=0)
    trans = librosa.sequence.transition_loop(len(etiquetas), 0.9)
    ids = librosa.sequence.viterbi_discriminative(prob, trans)
    dt = HOP / sr
    tramos, inicio = [], 0
    for i in range(1, len(ids) + 1):
        if i == len(ids) or ids[i] != ids[inicio]:
            tramos.append((inicio * dt, i * dt, etiquetas[ids[inicio]]))
            inicio = i
    return tramos


if __name__ == "__main__":
    for slug in SONGS:
        t0 = time.perf_counter()
        tramos = reconocer(wav_path(slug))
        seg = time.perf_counter() - t0
        guardar_linea("plantillas", slug, tramos, seg)
        print("plantillas", slug, len(tramos), "tramos", f"{seg:.1f}s", flush=True)
