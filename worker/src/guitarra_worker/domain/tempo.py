"""Tempo y compases a partir de una grilla de beats y downbeats (lógica pura, sin audio)."""

from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from statistics import median
from typing import Any

SECONDS_PER_MINUTE = 60.0
TIME_DECIMALS = 3
OUTLIER_RATIO = 0.25


def bpm_from_beats(beats: Sequence[float]) -> float | None:
    """BPM de la grilla. None si hay menos de 2 beats.

    El modelo marca los beats en cuadros de 20 ms: cada intervalo trae hasta +-2 % de error de
    cuantización, que se cancela al promediar. Por eso se promedian los intervalos y no se toma la
    mediana; los que se desvían más de `OUTLIER_RATIO` de la mediana (beat perdido o de más) se
    descartan antes.
    """
    if len(beats) < 2:
        return None
    intervals = [b - a for a, b in zip(beats, beats[1:], strict=False)]
    typical = median(intervals)
    steady = [i for i in intervals if abs(i - typical) <= typical * OUTLIER_RATIO]
    return SECONDS_PER_MINUTE * len(steady) / sum(steady)


def _nearest_beat_index(beats: Sequence[float], time_s: float) -> int:
    right = bisect_left(beats, time_s)
    if right == 0:
        return 0
    if right == len(beats):
        return len(beats) - 1
    return right if beats[right] - time_s < time_s - beats[right - 1] else right - 1


def beats_per_bar(beats: Sequence[float], downbeats: Sequence[float]) -> int | None:
    """Beats por compás: el largo más común entre downbeats consecutivos. None si no se puede."""
    if not beats or len(downbeats) < 2:
        return None
    indexes = [_nearest_beat_index(beats, t) for t in downbeats]
    lengths = [b - a for a, b in zip(indexes, indexes[1:], strict=False) if b > a]
    if not lengths:
        return None
    return Counter(lengths).most_common(1)[0][0]


def _rounded(values: Sequence[float]) -> list[float]:
    return [round(float(v), TIME_DECIMALS) for v in values]


def analyze_beats(beats: Sequence[float], downbeats: Sequence[float]) -> dict[str, Any]:
    """Resultado del paso de tempo. Sin beats devuelve campos vacíos: 'sin datos' no es un error."""
    bpm = bpm_from_beats(beats)
    return {
        "bpm": None if bpm is None else round(bpm, 2),
        "beats_per_bar": beats_per_bar(beats, downbeats),
        "beats": _rounded(beats),
        "downbeats": _rounded(downbeats),
        "first_beat_s": round(float(beats[0]), TIME_DECIMALS) if beats else None,
        "first_downbeat_s": round(float(downbeats[0]), TIME_DECIMALS) if downbeats else None,
    }
