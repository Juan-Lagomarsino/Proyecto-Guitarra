"""Cuantiza notas transcriptas (segundos) a la grilla de beats de una sección (lógica pura).

Salida en beats relativos al inicio de la sección (ADR 0018). Por cada beat se elige entre
semicorcheas (cuartos de beat) y tresillos de corchea (tercios) según el menor error de
redondeo. La duración de cada nota llega hasta el siguiente ataque, porque los offsets de
basic-pitch no son confiables (ADR 0017); así dos notas nunca se superponen en la misma altura.
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

GUITAR_MIN_MIDI = 40  # E2, cuerda 6 al aire (afinación estándar)
GUITAR_MAX_MIDI = 88  # E6, cuerda 1 en el traste 24
SIXTEENTH_STEPS = 4
TRIPLET_STEPS = 3
TRIPLET_MARGIN_BEATS = 0.01  # el tresillo tiene que ganar por más que esto; si no, semicorchea
MAX_NOTE_BEATS = 2.0
MIN_NOTE_BEATS = 1 / SIXTEENTH_STEPS
TIME_DECIMALS = 4
SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True)
class TimedNote:
    """Nota transcripta en segundos del audio completo."""

    onset_s: float
    offset_s: float
    midi: int
    confidence: float


@dataclass(frozen=True)
class BeatGrid:
    """Grilla de beats en segundos; sin grilla usable (< 2 beats) se usa `bpm`."""

    beats_s: Sequence[float]
    bpm: float | None = None


@dataclass(frozen=True)
class QuantizedEvent:
    midi: int
    t: float  # beats desde el inicio de la sección
    dur: float  # beats
    confidence: float


def _beat_position(grid: BeatGrid, seconds: float) -> float:
    """Posición en beats (el beat i de la grilla es la posición i); extrapola en los extremos."""
    beats = grid.beats_s
    if len(beats) < 2:
        if not grid.bpm:
            raise ValueError("Sin grilla de beats ni BPM no se puede cuantizar")
        return seconds * grid.bpm / SECONDS_PER_MINUTE
    right = min(max(bisect_right(beats, seconds), 1), len(beats) - 1)
    left = right - 1
    return left + (seconds - beats[left]) / (beats[right] - beats[left])


def _snap(fraction: float, steps: int) -> float:
    return round(fraction * steps) / steps


def _beat_error(fractions: Sequence[float], steps: int) -> float:
    return sum(abs(f - _snap(f, steps)) for f in fractions)


def _steps_for_beat(fractions: Sequence[float]) -> int:
    triplet = _beat_error(fractions, TRIPLET_STEPS)
    sixteenth = _beat_error(fractions, SIXTEENTH_STEPS)
    return TRIPLET_STEPS if triplet < sixteenth - TRIPLET_MARGIN_BEATS else SIXTEENTH_STEPS


def _snap_positions(positions: Sequence[float]) -> list[float]:
    """Redondea cada posición con la subdivisión que mejor le queda a su beat."""
    by_beat: dict[int, list[float]] = {}
    for position in positions:
        by_beat.setdefault(math.floor(position), []).append(position)
    steps = {b: _steps_for_beat([p - b for p in ps]) for b, ps in by_beat.items()}
    return [math.floor(p) + _snap(p - math.floor(p), steps[math.floor(p)]) for p in positions]


def _in_section(note: TimedNote, start_s: float, end_s: float) -> bool:
    in_range = GUITAR_MIN_MIDI <= note.midi <= GUITAR_MAX_MIDI
    return in_range and start_s <= note.onset_s < end_s


def _last_note_length(length: float) -> float:
    snapped = round(length * SIXTEENTH_STEPS) / SIXTEENTH_STEPS
    return min(max(snapped, MIN_NOTE_BEATS), MAX_NOTE_BEATS)


def quantize_section(
    notes: Sequence[TimedNote], start_s: float, end_s: float, grid: BeatGrid
) -> list[QuantizedEvent]:
    """Eventos de la sección `[start_s, end_s)`, ordenados por `t` y altura."""
    start_beat = _beat_position(grid, start_s)
    section_beats = _beat_position(grid, end_s) - start_beat
    inside = [n for n in notes if _in_section(n, start_s, end_s)]
    # Se agrupa y redondea en beats absolutos de la grilla: la sección puede no empezar en un beat.
    positions = [_beat_position(grid, n.onset_s) for n in inside]
    # el ataque está dentro de la sección, pero el redondeo puede dejarlo un pelo antes: pasa a 0
    snapped = [max(round(p - start_beat, TIME_DECIMALS), 0.0) for p in _snap_positions(positions)]

    best: dict[tuple[float, int], tuple[float, float]] = {}  # (t, midi) -> (conf, length)
    for note, t in zip(inside, snapped, strict=True):
        if t >= section_beats:
            continue
        length = _beat_position(grid, note.offset_s) - _beat_position(grid, note.onset_s)
        confidence = min(max(note.confidence, 0.0), 1.0)
        if (t, note.midi) not in best or confidence > best[(t, note.midi)][0]:
            best[(t, note.midi)] = (confidence, length)

    onsets = sorted({t for t, _ in best})
    next_onset = dict(zip(onsets, onsets[1:], strict=False))
    events = []
    for (t, midi), (confidence, length) in sorted(best.items()):
        following = next_onset.get(t)
        dur = following - t if following is not None else _last_note_length(length)
        dur = round(min(dur, MAX_NOTE_BEATS, section_beats - t), TIME_DECIMALS)
        if dur < MIN_NOTE_BEATS:  # la API exige dur > 0; una nota casi al final no entra
            continue
        events.append(QuantizedEvent(midi, t, dur, confidence))
    return events
