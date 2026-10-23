"""Línea de tiempo de acordes ajustada a la grilla de beats (lógica pura, sin audio ni modelos).

El reconocedor (BTC) devuelve tramos con tiempos libres. Acá se asigna a cada beat el acorde que
más lo cubre, se unen los beats vecinos con el mismo acorde y se calcula la confianza de cada tramo
como la fracción promedio del beat que cubría el acorde ganador. Un acorde que dura menos que un
beat nunca gana un beat entero salvo que cubra la mayoría: queda absorbido por el vecino.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from guitarra_core.theory import ChordParseError, lenient_chord, parse_chord

NO_CHORD = "N"


@dataclass(frozen=True)
class RawChord:
    """Un tramo tal como lo devuelve el reconocedor (etiqueta en notación Harte, ej. `A:min7`)."""

    start: float
    end: float
    label: str


@dataclass(frozen=True)
class ChordSpan:
    """Un tramo ajustado a la grilla. `label` es el nombre canónico o "N" si no hay acorde."""

    start: float
    end: float
    label: str
    confidence: float


def normalize_label(label: str) -> str:
    """Etiqueta del reconocedor a nombre canónico del core; lo que no se entiende es "N"."""
    try:
        chord = parse_chord(label)
    except ChordParseError:
        chord = lenient_chord(label)
    return chord.name if chord else NO_CHORD


def snap_to_beats(
    raw: Sequence[RawChord], beats: Sequence[float], duration_s: float | None = None
) -> list[ChordSpan]:
    """Ajusta los tramos a la grilla. Devuelve [] si hay menos de 2 beats."""
    cells = _beat_cells(beats, duration_s)
    labelled = [RawChord(r.start, r.end, normalize_label(r.label)) for r in raw]
    voted: list[tuple[float, float, str, float]] = []
    previous: str | None = None
    for start, end in cells:
        label, coverage = _vote(labelled, start, end, previous)
        voted.append((start, end, label, coverage))
        previous = label
    return _merge_neighbours(voted)


def _beat_cells(beats: Sequence[float], duration_s: float | None) -> list[tuple[float, float]]:
    times = sorted(set(beats))
    if len(times) < 2:
        return []
    period = median(b - a for a, b in zip(times, times[1:], strict=False))
    edges = [*times, times[-1] + period]
    cells = list(zip(edges, edges[1:], strict=False))
    if duration_s is None:
        return cells
    return [(a, min(b, duration_s)) for a, b in cells if a < duration_s]


def _vote(
    raw: Sequence[RawChord], start: float, end: float, previous: str | None
) -> tuple[str, float]:
    """Acorde que más cubre [start, end) y qué fracción cubre. Empate: el del beat previo."""
    overlap: dict[str, float] = defaultdict(float)
    for chord in raw:
        covered = min(chord.end, end) - max(chord.start, start)
        if covered > 0:
            overlap[chord.label] += covered
    if not overlap:
        return NO_CHORD, 0.0
    best = max(overlap.values())
    winners = [label for label, value in overlap.items() if value == best]
    label = previous if previous in winners else winners[0]
    return label, min(1.0, best / (end - start))


def _merge_neighbours(voted: Sequence[tuple[float, float, str, float]]) -> list[ChordSpan]:
    spans: list[ChordSpan] = []
    group: list[tuple[float, float, str, float]] = []
    for cell in voted:
        if group and cell[2] != group[0][2]:
            spans.append(_close(group))
            group = []
        group.append(cell)
    if group:
        spans.append(_close(group))
    return spans


def _close(group: Sequence[tuple[float, float, str, float]]) -> ChordSpan:
    total = sum(end - start for start, end, _, _ in group)
    weighted = sum((end - start) * coverage for start, end, _, coverage in group)
    return ChordSpan(group[0][0], group[-1][1], group[0][2], weighted / total if total else 0.0)
