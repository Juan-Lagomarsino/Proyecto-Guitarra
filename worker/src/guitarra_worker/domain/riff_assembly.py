"""Arma la notación de un riff a partir de las notas cuantizadas (lógica pura).

Entrada: `{section_id: [{midi, t, dur, confidence}]}` con `t`/`dur` en beats relativos a la sección.
Salida: `{section_id: Notation}` (formato único de `schemas/notation.schema.json`), con cuerda y
traste elegidos por la digitación de `guitarra_core` (afinación estándar, capo del chart y
preferencias aprendidas).

Qué se hace con lo que no se puede tocar:
- una nota fuera del rango de la guitarra (con ese capo) se descarta;
- un paso (notas simultáneas) que no entra en la mano se simplifica: se va soltando la nota de
  menor confianza; ante un empate se sueltan primero las del medio, así quedan la más grave y la
  más aguda, hasta que el paso entre.
Las secciones que quedan sin eventos no van en la salida.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from guitarra_core.fingering import (
    STANDARD_TUNING,
    FingeringError,
    FingeringPreferences,
    FingeringStep,
    Placement,
    finger_steps,
)

TUNING_NAMES = ["E2", "A2", "D3", "G3", "B3", "E4"]  # igual que STANDARD_TUNING en la API
Event = Mapping[str, Any]


@dataclass(frozen=True)
class RiffChart:
    """Lo que el armado necesita del chart."""

    bpm: float
    time_signature: str = "4/4"
    capo: int = 0


@dataclass(frozen=True)
class _Note:
    midi: int
    dur: float
    confidence: float


def _playable(notes: Sequence[_Note], capo: int) -> bool:
    step = FingeringStep(tuple(n.midi for n in notes))
    try:
        finger_steps([step], tuning=STANDARD_TUNING, capo=capo)
    except FingeringError:
        return False
    return True


def _drop_index(notes: Sequence[_Note]) -> int:
    """Nota a soltar: menor confianza; en empate una del medio y, si no, la más aguda."""
    ordered = sorted(range(len(notes)), key=lambda i: notes[i].midi)
    extremes = {ordered[0], ordered[-1]}
    return min(
        range(len(notes)), key=lambda i: (notes[i].confidence, i in extremes, -notes[i].midi)
    )


def simplify_step(notes: Sequence[_Note], capo: int) -> list[_Note]:
    """Las notas del paso que sí se pueden tocar a la vez ([] si ninguna se puede tocar)."""
    kept = [n for n in notes if _playable([n], capo)]  # descarta las imposibles
    while len(kept) > 1 and not _playable(kept, capo):
        kept.pop(_drop_index(kept))
    return kept


def _steps_of(events: Sequence[Event], capo: int) -> list[tuple[float, list[_Note]]]:
    """Agrupa por `t` (ordenado) y simplifica; los pasos sin notas tocables se omiten."""
    by_time: dict[float, dict[int, _Note]] = defaultdict(dict)
    for e in events:
        note = _Note(int(e["midi"]), float(e["dur"]), float(e["confidence"]))
        current = by_time[float(e["t"])].get(note.midi)
        if current is None or note.confidence > current.confidence:
            by_time[float(e["t"])][note.midi] = note
    steps = [(t, simplify_step(list(n.values()), capo)) for t, n in sorted(by_time.items())]
    return [(t, notes) for t, notes in steps if notes]


def _event(t: float, note: _Note, placement: Placement) -> dict[str, Any]:
    return {
        "t": t,
        "dur": note.dur,
        "string": placement.string,
        "fret": placement.fret,
        "technique": None,
        "confidence": note.confidence,
    }


def build_riff(
    events: Sequence[Event], chart: RiffChart, preferences: FingeringPreferences
) -> dict[str, Any] | None:
    steps = _steps_of(events, chart.capo)
    if not steps:
        return None
    placements = finger_steps(
        [FingeringStep(tuple(n.midi for n in notes)) for _, notes in steps],
        tuning=STANDARD_TUNING,
        capo=chart.capo,
        preferences=preferences,
    )
    out = [
        _event(t, note, placement)
        for (t, notes), step_placements in zip(steps, placements, strict=True)
        for note, placement in sorted(
            zip(notes, step_placements, strict=True), key=lambda pair: -pair[1].string
        )
    ]
    return {
        "tuning": list(TUNING_NAMES),
        "bpm": chart.bpm,
        "time_signature": chart.time_signature,
        "events": out,
        "tonic": None,
    }


def build_riffs(
    events_by_section: Mapping[str, Sequence[Event]],
    chart: RiffChart,
    preferences: FingeringPreferences | None = None,
) -> dict[str, dict[str, Any]]:
    prefs = preferences or FingeringPreferences()
    riffs = {sid: build_riff(events, chart, prefs) for sid, events in events_by_section.items()}
    return {sid: riff for sid, riff in riffs.items() if riff is not None}
