"""Estructura de una canción a partir de su matriz de autosimilitud por beat.

Lógica pura (sin librosa ni audio): la matriz la arma un adaptador. Pasos:
1. Novedad con kernel de tablero de ajedrez sobre la diagonal -> beats donde cambia el material.
2. Los límites se ajustan al downbeat más cercano (secciones alineadas a compases).
3. Las secciones parecidas entre sí se agrupan (A, B, C...).
4. Nombres heurísticos según repetición y posición. Sin repeticiones no se inventan nombres.

La detección sola es floja (ADR 0006): la confianza nunca pasa de "media" y Cifra Club (T13)
pisa nombres y orden cuando existe.
"""

import string
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy.signal import find_peaks

DEFAULT_BEATS_PER_BAR = 4
KERNEL_BARS = 8  # semiancho del kernel de novedad
MIN_SECTION_BARS = 4
SIMILARITY_THRESHOLD = 0.5  # afinidad media para decir "es la misma sección"
MIN_LENGTH_RATIO = 0.6  # dos secciones de largo muy distinto no son la misma
PROMINENCE_STD_FACTOR = 0.5
MIN_SONG_SECTIONS = 4  # menos de 4 secciones mínimas de largo: no se segmenta
MAX_KERNEL_FRACTION = 4  # el semiancho del kernel no pasa de n / 4 beats
EPSILON_S = 1e-6  # tolerancia al comparar tiempos en segundos con la grilla de beats

Confidence = Literal["baja", "media"]


@dataclass(frozen=True)
class Section:
    order: int
    start_s: float
    end_s: float
    start_bar: int
    end_bar: int
    group: str
    name: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "start_s": round(self.start_s, 3),
            "end_s": round(self.end_s, 3),
            "start_bar": self.start_bar,
            "end_bar": self.end_bar,
            "group": self.group,
            "name": self.name,
        }


@dataclass(frozen=True)
class StructureResult:
    sections: list[Section]
    confidence: Confidence


def _novelty_curve(ssm: np.ndarray, half: int) -> np.ndarray:
    signs = np.r_[-np.ones(half), np.ones(half)]
    kernel = np.outer(signs, signs)
    padded = np.pad(ssm, half, mode="edge")
    return np.array(
        [(padded[i : i + 2 * half, i : i + 2 * half] * kernel).sum() for i in range(len(ssm))]
    )


def detect_boundaries(
    ssm: np.ndarray, beats_per_bar: int, kernel_bars: int = KERNEL_BARS
) -> list[int]:
    """Índices de beat donde empieza una sección nueva (sin contar el 0)."""
    n = len(ssm)
    min_beats = MIN_SECTION_BARS * beats_per_bar
    if n < MIN_SONG_SECTIONS * min_beats:  # canción muy corta: una sola sección
        return []
    half = min(kernel_bars * beats_per_bar, n // MAX_KERNEL_FRACTION)
    curve = _novelty_curve(ssm, half)
    peaks, _ = find_peaks(curve, distance=min_beats, prominence=curve.std() * PROMINENCE_STD_FACTOR)
    return [int(p) for p in peaks if min_beats <= p <= n - min_beats]


def snap_to_downbeats(times: np.ndarray, downbeats: np.ndarray) -> np.ndarray:
    """Lleva cada tiempo al downbeat más cercano; sin duplicados, ordenado."""
    if len(times) == 0 or len(downbeats) == 0:
        return np.array([])
    nearest = np.abs(downbeats[None, :] - times[:, None]).argmin(axis=1)
    return np.unique(downbeats[nearest])


def _beats_per_bar(beats: np.ndarray, downbeats: np.ndarray) -> int:
    if len(downbeats) < 2:
        return DEFAULT_BEATS_PER_BAR
    positions = np.searchsorted(beats, downbeats - EPSILON_S)
    return max(1, int(round(float(np.median(np.diff(positions))))))


def _section_edges(snapped: np.ndarray, downbeats: np.ndarray, duration_s: float) -> list[float]:
    """Inicios de sección (con 0.0 al principio) separados al menos MIN_SECTION_BARS compases."""
    edges = [0.0]
    last_bar = 0
    for time in snapped:
        bar = int(np.searchsorted(downbeats, time - EPSILON_S))
        far_from_previous = bar - last_bar >= MIN_SECTION_BARS
        if 0 < time < duration_s and bar > 0 and far_from_previous:
            edges.append(float(time))
            last_bar = bar
    return edges


def _affinity(ssm: np.ndarray, a: tuple[int, int], b: tuple[int, int]) -> float:
    len_a, len_b = a[1] - a[0], b[1] - b[0]
    if min(len_a, len_b) == 0 or min(len_a, len_b) / max(len_a, len_b) < MIN_LENGTH_RATIO:
        return 0.0
    length = min(len_a, len_b)
    block = ssm[a[0] : a[0] + length, b[0] : b[0] + length]
    return float(np.diagonal(block).mean())


def _group_labels(ssm: np.ndarray, spans: list[tuple[int, int]]) -> list[int]:
    """Número de grupo por sección; la primera de cada grupo es su representante."""
    representatives: list[int] = []
    groups: list[int] = []
    for i, span in enumerate(spans):
        for g, rep in enumerate(representatives):
            if _affinity(ssm, spans[rep], span) >= SIMILARITY_THRESHOLD:
                groups.append(g)
                break
        else:
            representatives.append(i)
            groups.append(len(representatives) - 1)
    return groups


def _group_letter(group: int) -> str:
    letters = string.ascii_uppercase
    return letters[group] if group < len(letters) else f"G{group}"


def _heuristic_names(groups: list[int]) -> list[str | None]:
    counts = {g: groups.count(g) for g in set(groups)}
    repeated = {g for g, count in counts.items() if count >= 2}
    if not repeated:
        return [None] * len(groups)
    chorus = max(repeated, key=lambda g: (counts[g], groups.index(g)))
    last = len(groups) - 1
    names: list[str | None] = []
    for i, g in enumerate(groups):
        if g == chorus:
            names.append("estribillo")
        elif g in repeated:
            names.append("estrofa")
        elif i == 0:
            names.append("intro")
        elif i == last:
            names.append("final")
        else:
            names.append("puente")
    return names


def analyze_structure(
    ssm: np.ndarray, beats: np.ndarray, downbeats: np.ndarray, duration_s: float
) -> StructureResult:
    """Secciones con inicio, fin, orden, compás y nombre a partir de la autosimilitud por beat."""
    if len(beats) == 0 or len(downbeats) == 0:
        return StructureResult([], "baja")
    per_bar = _beats_per_bar(beats, downbeats)
    boundary_times = beats[detect_boundaries(ssm, per_bar)]
    snapped = snap_to_downbeats(boundary_times, downbeats)
    starts = _section_edges(snapped, downbeats, duration_s)
    ends = [*starts[1:], duration_s]

    beat_cuts = [int(np.searchsorted(beats, t - EPSILON_S)) for t in starts] + [len(beats)]
    spans = list(zip(beat_cuts[:-1], beat_cuts[1:], strict=True))
    groups = _group_labels(ssm, spans)
    names = _heuristic_names(groups)

    bar_cuts = [int(np.searchsorted(downbeats, t - EPSILON_S)) for t in starts] + [len(downbeats)]
    sections = [
        Section(
            order=i,
            start_s=start,
            end_s=end,
            start_bar=bar_cuts[i],
            end_bar=bar_cuts[i + 1],
            group=_group_letter(groups[i]),
            name=names[i],
        )
        for i, (start, end) in enumerate(zip(starts, ends, strict=True))
    ]
    confidence: Confidence = "media" if any(names) else "baja"
    return StructureResult(sections, confidence)
