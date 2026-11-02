"""Mezcla "sin guitarra": suma de todas las pistas de Demucs menos la guitarra.

Pura (solo numpy): se testea sin Demucs. La normalización es una sola ganancia global, así el
balance entre pistas queda igual y la mezcla nunca pasa de -1 dBFS.
"""

import numpy as np

STEM_NAMES = ("drums", "bass", "other", "vocals", "guitar", "piano")  # htdemucs_6s
GUITAR = "guitar"
PEAK_LIMIT = 10 ** (-1 / 20)  # -1 dBFS


def mix_without_guitar(stems: dict[str, np.ndarray]) -> np.ndarray:
    """Suma las pistas que no son la guitarra (arrays `(muestras, canales)` float).

    Exige las seis pistas: si falta alguna, la mezcla sería otra cosa sin avisar.
    """
    missing = [name for name in STEM_NAMES if name not in stems]
    if missing:
        raise ValueError(f"Faltan pistas para mezclar: {', '.join(missing)}")
    length = min(len(stem) for stem in stems.values())
    mixed = np.zeros_like(stems["drums"][:length], dtype=np.float64)
    for name in STEM_NAMES:
        if name != GUITAR:
            mixed += stems[name][:length]
    return _limit_peak(mixed).astype(np.float32)


def _limit_peak(signal: np.ndarray) -> np.ndarray:
    peak = float(np.abs(signal).max()) if signal.size else 0.0
    return signal * (PEAK_LIMIT / peak) if peak > PEAK_LIMIT else signal
