"""Métricas de transcripción de notas con mir_eval y lectura de la referencia."""

import json
from pathlib import Path

import mir_eval
import numpy as np

ONSET_TOL = 0.05  # s
PITCH_TOL_CENTS = 50.0  # altura exacta al semitono


def leer_referencia(ruta: Path) -> np.ndarray:
    """Referencia como array (N, 3): onset, offset, midi.

    Formatos (ver README):
      - JSON: {"notas": [{"onset": 0.5, "offset": 0.9, "midi": 64}, ...]}
      - TSV/texto: una nota por línea `onset<TAB>offset<TAB>midi`; `#` comenta; espacios sirven.
    """
    if ruta.suffix.lower() == ".json":
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        filas = [(n["onset"], n["offset"], n["midi"]) for n in datos["notas"]]
    else:
        filas = []
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.split("#")[0].strip()
            if linea:
                onset, offset, midi = linea.replace(",", " ").split()[:3]
                filas.append((float(onset), float(offset), float(midi)))
    return np.array(sorted(filas), dtype=float).reshape(-1, 3)


def _hz(midis: np.ndarray) -> np.ndarray:
    return 440.0 * 2.0 ** ((midis - 69) / 12)


def evaluar(ref: np.ndarray, est: np.ndarray) -> dict[str, float]:
    """P/R/F1 sin offsets y con offsets (offset dentro de 20 % de la duración o 50 ms)."""
    if len(est) == 0 or len(ref) == 0:
        return dict.fromkeys(("p", "r", "f1", "p_off", "r_off", "f1_off"), 0.0)
    args = (ref[:, :2], _hz(ref[:, 2]), est[:, :2], _hz(est[:, 2]))
    comun = {"onset_tolerance": ONSET_TOL, "pitch_tolerance": PITCH_TOL_CENTS}
    p, r, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        *args, offset_ratio=None, **comun
    )
    p2, r2, f2, _ = mir_eval.transcription.precision_recall_f1_overlap(*args, **comun)
    return {"p": p, "r": r, "f1": f1, "p_off": p2, "r_off": r2, "f1_off": f2}
