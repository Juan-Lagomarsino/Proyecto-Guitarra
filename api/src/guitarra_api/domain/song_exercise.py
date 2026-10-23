"""Arma la notación de un ejercicio a partir de una sección del chart (ADR 0003 y 0008).

Los tiempos del ejercicio van en beats desde el primer acorde de la sección. Es dominio puro:
no conoce la base ni FastAPI.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from guitarra_api.domain.notation import Chord, Notation, Strum
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
    to_beats = _beats_converter(content, origin_s=chords[0].t_s)
    strum_events, window = _strum_events(content, section, to_beats(section.end_s), kind)
    chord_events = [
        _chord(chord, to_beats(chord.t_s)) for chord in chords if to_beats(chord.t_s) < window
    ]
    notation = Notation(
        bpm=bpm_start,
        time_signature=content.time_signature,
        chords=chord_events,
        strum=strum_events,
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
    numerator = time_signature.split("/")[0]
    return int(numerator) if numerator.isdigit() and int(numerator) > 0 else DEFAULT_BEATS_PER_BAR


def _strum_events(
    content: SongChartContent, section: ChartSection, section_beats: float, kind: str
) -> tuple[list[Strum], float]:
    """Eventos de rasgueo y largo del ejercicio en beats (el patrón se repite por ciclo)."""
    length = min(max(section_beats, 1.0), MAX_EXERCISE_BEATS)
    if kind != "strumming" or section.strum is None:
        return [], length
    strum = section.strum
    cycle = strum.beats_per_cycle or _beats_per_bar(content.time_signature)
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
