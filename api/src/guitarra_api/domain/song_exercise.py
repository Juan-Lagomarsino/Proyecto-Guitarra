"""Arma la notación de un ejercicio a partir de una sección del chart (ADR 0003 y 0008).

Los tiempos del ejercicio van en beats desde el inicio de la sección (`start_s`), el mismo
origen que usa la UI para sincronizar con el audio. Es dominio puro:
no conoce la base ni FastAPI.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from guitarra_api.domain.notation import Chord, Notation, NoteEvent, Strum
from guitarra_api.domain.song_chart import (
    ChartChord,
    ChartSection,
    SongChartContent,
    seconds_to_beats,
)

SectionExerciseKind = Literal["chords", "strumming"]

START_BPM_RATIO = 0.7
MAX_EXERCISE_BEATS = 32.0
DEFAULT_DURATION_MIN = 5
DEFAULT_BEATS_PER_BAR = 4
BEAT_DECIMALS = 3
CYCLE_EPSILON = 1e-9
BEATS_PER_BAR = {"4/4": 4, "3/4": 3, "6/8": 2}  # misma regla que gridBeatsPerBar en la UI
SOUNDING_STROKES = "DU"
_KIND_LABELS = {"chords": "cambio de acordes", "strumming": "rasgueo"}


class SectionNotFoundInChartError(Exception):
    def __init__(self, section_id: str) -> None:
        super().__init__(f"La sección '{section_id}' ya no está en el chart vigente")


class SectionNotPlayableError(Exception):
    """La sección no tiene lo necesario para armar ese tipo de ejercicio."""


@dataclass(frozen=True)
class SectionExercise:
    title_suffix: str
    notation: Notation
    bpm_start: int
    bpm_target: int
    duration_min: int
    description: str


def build_section_exercise(
    content: SongChartContent, section_id: str, kind: SectionExerciseKind
) -> SectionExercise:
    """Raises: SectionNotFoundInChartError, SectionNotPlayableError."""
    section = _find_section(content, section_id)
    chords = _distinct_consecutive(section.chords)
    if not chords:
        raise SectionNotPlayableError(f"La sección '{section.name}' no tiene acordes")
    if kind == "strumming" and section.strum is None:
        raise SectionNotPlayableError(f"La sección '{section.name}' no tiene rasgueo")

    bpm_start, bpm_target = suggested_bpm(content.bpm)
    to_beats = _beats_converter(content, origin_s=section.start_s)
    strum_events, window = _strum_events(content, section, to_beats(section.end_s), kind)
    chord_events = [
        _chord(chord, max(0.0, to_beats(chord.t_s)))
        for chord in chords
        if to_beats(chord.t_s) < window
    ]
    notation = Notation(
        bpm=bpm_start,
        time_signature=content.time_signature,
        chords=chord_events,
        strum=strum_events,
        events=chords_as_events(
            chord_events,
            strum_events,
            window,
            cycle=_strum_cycle(content, section),
            bar_beats=_beats_per_bar(content.time_signature),
        ),
    )
    return SectionExercise(
        title_suffix=f"{section.name}: {_KIND_LABELS[kind]}",
        notation=notation,
        bpm_start=bpm_start,
        bpm_target=bpm_target,
        duration_min=DEFAULT_DURATION_MIN,
        description=_description(kind, bpm_start, bpm_target),
    )


def suggested_bpm(song_bpm: float) -> tuple[int, int]:
    """(bpm de arranque, bpm objetivo): el arranque es un porcentaje del tempo de la canción."""
    target = max(1, round(song_bpm))
    return max(1, min(target, round(song_bpm * START_BPM_RATIO))), target


def _find_section(content: SongChartContent, section_id: str) -> ChartSection:
    for section in content.sections:
        if section.id == section_id:
            return section
    raise SectionNotFoundInChartError(section_id)


def _distinct_consecutive(chords: list[ChartChord]) -> list[ChartChord]:
    result: list[ChartChord] = []
    for chord in chords:
        if not result or (result[-1].name, result[-1].shape) != (chord.name, chord.shape):
            result.append(chord)
    return result


def _beats_converter(content: SongChartContent, origin_s: float) -> Callable[[float], float]:
    grid = content.beat_grid
    if grid is None:
        return lambda t_s: round((t_s - origin_s) * content.bpm / 60, BEAT_DECIMALS)
    origin = seconds_to_beats(origin_s, grid)
    return lambda t_s: round(seconds_to_beats(t_s, grid) - origin, BEAT_DECIMALS)


def _chord(chord: ChartChord, t: float) -> Chord:
    return Chord(t=t, name=chord.name, shape=chord.shape, barre=chord.barre)


def _beats_per_bar(time_signature: str) -> int:
    return BEATS_PER_BAR.get(time_signature, DEFAULT_BEATS_PER_BAR)


def _strum_cycle(content: SongChartContent, section: ChartSection) -> float:
    cycle = section.strum.beats_per_cycle if section.strum else None
    return cycle or _beats_per_bar(content.time_signature)


def _strum_events(
    content: SongChartContent, section: ChartSection, section_beats: float, kind: str
) -> tuple[list[Strum], float]:
    """Eventos de rasgueo y largo del ejercicio en beats (el patrón se repite por ciclo)."""
    length = min(max(section_beats, 1.0), MAX_EXERCISE_BEATS)
    if kind != "strumming" or section.strum is None:
        return [], length
    strum = section.strum
    cycle = _strum_cycle(content, section)
    # Ciclos completos hacia arriba (no se pierden los acordes del final), con el tope de beats.
    wanted = math.ceil(length / cycle - CYCLE_EPSILON)
    cycles = max(1, min(wanted, int(MAX_EXERCISE_BEATS // cycle)))
    events = [
        Strum(t=round(index * cycle, BEAT_DECIMALS), pattern=strum.pattern, accent=strum.accent)
        for index in range(cycles)
    ]
    return events, cycles * cycle


def _description(kind: SectionExerciseKind, bpm_start: int, bpm_target: int) -> str:
    what = (
        "Pasá de un acorde al siguiente sin cortar el tempo."
        if kind == "chords"
        else "Rasguá el patrón de la sección sobre su progresión."
    )
    return f"{what} Empezá a {bpm_start} bpm y subí hasta {bpm_target}, el tempo de la canción."


def chords_as_events(
    chords: list[Chord],
    strums: list[Strum],
    window: float,
    cycle: float,
    bar_beats: float = DEFAULT_BEATS_PER_BAR,
) -> list[NoteEvent]:
    """Acordes como notas: una por cuerda que suena (las `x` no). Con rasgueo, el acorde vigente
    se repite en cada golpe D/U del patrón (`-` no suena); sin rasgueo dura hasta el próximo."""
    if not chords:
        return []
    if not strums:
        return _sustained(chords, window)
    events: list[NoteEvent] = []
    for strum in strums:
        cell = cycle / len(strum.pattern)
        for index, stroke in enumerate(strum.pattern):
            at = round(strum.t + index * cell, BEAT_DECIMALS)
            chord = _chord_at(chords, at)
            if stroke in SOUNDING_STROKES and chord is not None and at < window:
                events.extend(_notes(chord, at, round(cell, BEAT_DECIMALS)))
    return events


def complete_with_events(notation: Notation) -> Notation:
    """Ejercicios guardados antes de "acordes como notas": deriva `events` de `chords` y `strum`."""
    if notation.events or not notation.chords:
        return notation
    bar_beats = BEATS_PER_BAR.get(notation.time_signature, DEFAULT_BEATS_PER_BAR)
    strums = notation.strum
    cycle = strums[1].t - strums[0].t if len(strums) > 1 else bar_beats
    window = strums[-1].t + cycle if strums else notation.chords[-1].t + bar_beats
    events = chords_as_events(notation.chords, strums, window, cycle, bar_beats)
    return notation.model_copy(update={"events": events})


def _chord_at(chords: list[Chord], at: float) -> Chord | None:
    current = None
    for chord in chords:
        if chord.t <= at + CYCLE_EPSILON:
            current = chord
    return current


def _sustained(chords: list[Chord], window: float) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for index, chord in enumerate(chords):
        end = chords[index + 1].t if index + 1 < len(chords) else window
        if end > chord.t:
            events.extend(_notes(chord, chord.t, round(end - chord.t, BEAT_DECIMALS)))
    return events


def _notes(chord: Chord, at: float, dur: float) -> list[NoteEvent]:
    """Cuerdas de la forma, de la 6 (grave) a la 1; la forma va de la grave a la aguda."""
    return [
        NoteEvent(t=at, dur=dur, string=6 - index, fret=fret)
        for index, fret in enumerate(chord.shape)
        if fret != "x"
    ]
