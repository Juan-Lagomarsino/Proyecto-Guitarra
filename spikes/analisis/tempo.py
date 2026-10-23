"""Tempo y compases: beat_this, librosa y madmom. Guarda resultados/tempo.json."""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from songs import SONGS, wav_path

SALIDA = Path(__file__).parent / "resultados" / "tempo.json"


def bpm_de_beats(beats: np.ndarray) -> float:
    return float(60.0 / np.median(np.diff(beats)))


def compas_de(beats: np.ndarray, downbeats: np.ndarray) -> float | None:
    """Beats por compás (mediana de beats entre downbeats consecutivos)."""
    if len(downbeats) < 2:
        return None
    idx = np.searchsorted(beats, downbeats - 1e-3)
    return float(np.median(np.diff(idx)))


def con_beat_this(ruta: Path) -> dict:
    from beat_this.inference import File2Beats

    if not hasattr(con_beat_this, "modelo"):
        ckpt = os.environ.get("BEAT_THIS_CKPT", "final0")
        con_beat_this.modelo = File2Beats(checkpoint_path=ckpt, device="cpu", dbn=False)
    beats, downbeats = con_beat_this.modelo(str(ruta))
    return {"beats": np.asarray(beats), "downbeats": np.asarray(downbeats)}


def con_librosa(ruta: Path) -> dict:
    import librosa

    y, sr = librosa.load(str(ruta), sr=22050, mono=True)
    _, frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(frames, sr=sr)
    # librosa no estima downbeats: se asume 4/4 con fase 0 (limitación a medir).
    return {"beats": beats, "downbeats": beats[::4]}


def con_madmom(ruta: Path) -> dict:
    from madmom.features.downbeats import (
        DBNDownBeatTrackingProcessor,
        RNNDownBeatProcessor,
    )

    act = RNNDownBeatProcessor()(str(ruta))
    res = DBNDownBeatTrackingProcessor(beats_per_bar=[3, 4], fps=100)(act)
    return {"beats": res[:, 0], "downbeats": res[res[:, 1] == 1, 0]}


HERRAMIENTAS = {
    "beat_this": con_beat_this,
    "librosa": con_librosa,
    "madmom": con_madmom,
}


def guardar_beats(nombre: str, slug: str, r: dict) -> None:
    destino = SALIDA.parent / "beats" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    datos = {k: [round(float(t), 3) for t in v] for k, v in r.items()}
    (destino / f"{slug}.json").write_text(json.dumps(datos), encoding="utf-8")


def medir(nombre: str) -> dict:
    out = {}
    for slug in SONGS:
        t0 = time.perf_counter()
        try:
            r = HERRAMIENTAS[nombre](wav_path(slug))
            seg = time.perf_counter() - t0
            guardar_beats(nombre, slug, r)
            out[slug] = {
                "bpm": bpm_de_beats(r["beats"]),
                "beats_por_compas": compas_de(r["beats"], r["downbeats"]),
                "primer_beat": float(r["beats"][0]),
                "n_beats": len(r["beats"]),
                "segundos": seg,
            }
        except Exception as e:  # noqa: BLE001 - el spike registra el fallo y sigue
            out[slug] = {"error": repr(e)}
        print(nombre, slug, out[slug], flush=True)
    return out


if __name__ == "__main__":
    SALIDA.parent.mkdir(exist_ok=True)
    previo = json.loads(SALIDA.read_text()) if SALIDA.exists() else {}
    for nombre in sys.argv[1:]:
        previo[nombre] = medir(nombre)
    SALIDA.write_text(json.dumps(previo, indent=2))
