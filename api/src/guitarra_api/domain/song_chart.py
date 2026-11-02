"""Contenido de un `SongChart` (fuente de verdad del JSON Schema y de los tipos TS). Ver ADR 0008.

Todo el tiempo del chart está en **segundos** desde el inicio de la canción (`*_s`); la grilla de
beats (`beat_grid`) permite pasar a beats con `seconds_to_beats`. El rasgueo y el arpegio no son una
línea de tiempo sino un patrón que se repite en la sección.
"""

import bisect
from statistics import fmean
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from guitarra_api.domain.app_settings import Instrument
from guitarra_api.domain.notation import (
    NOTE_PATTERN,
    Barre,
    ChordName,
    ChordShape,
    NoFieldTitles,
    Notation,
    StrumAccents,
    StrumPattern,
    ensure_accents_inside_pattern,
)

SECTION_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"
ARPEGGIO_PATTERN = r"^[pima](-[pima])*$"
MAX_CAPO_FRET = 12
MAX_BPM = 400
BEAT_TOLERANCE_S = 0.01
RIFF_TOLERANCE_BEATS = 0.01

Confidence = Annotated[float, Field(ge=0, le=1)]
Seconds = Annotated[float, Field(ge=0)]
ChordSource = Literal["detected", "cifraclub", "user"]
Mode = Literal["major", "minor"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChartChord(_Strict):
    """Acorde con el mismo `name`, `shape` y `barre` que la notación; `t_s` en segundos."""

    t_s: Seconds
    name: ChordName
    shape: ChordShape
    barre: Barre | None = None
    confidence: Confidence


class SectionStrum(_Strict):
    """Rasgueo propuesto: un patrón que se repite, con el patrón del catálogo del que salió."""

    pattern: StrumPattern
    accent: StrumAccents = Field(default_factory=list)
    beats_per_cycle: Annotated[float, Field(gt=0)] | None = None
    pattern_id: Annotated[str, Field(min_length=1)]
    confidence: Confidence

    @model_validator(mode="after")
    def _accents_point_inside_pattern(self) -> Self:
        ensure_accents_inside_pattern(self.pattern, self.accent)
        return self


class SectionArpeggio(_Strict):
    """Arpegio p-i-m-a (solo guitarra clásica), p. ej. `p-i-m-a-m-i`."""

    pattern_id: Annotated[str, Field(min_length=1)]
    pattern: Annotated[str, Field(pattern=ARPEGGIO_PATTERN)]
    confidence: Confidence


class ChartSection(_Strict):
    id: Annotated[str, Field(pattern=SECTION_ID_PATTERN)]
    name: Annotated[str, Field(min_length=1)]
    start_s: Seconds
    end_s: Seconds
    order: Annotated[int, Field(ge=0)]
    chord_source: ChordSource
    chords: list[ChartChord] = Field(default_factory=list)
    strum: SectionStrum | None = None
    arpeggio: SectionArpeggio | None = None
    riff: Notation | None = None

    @field_validator("name")
    @classmethod
    def _name_is_not_blank(cls, name: str) -> str:
        if not name.strip():
            raise ValueError("el nombre de la sección no puede ser solo espacios")
        return name

    @model_validator(mode="after")
    def _start_is_before_end(self) -> Self:
        if self.start_s >= self.end_s:
            raise ValueError(f"sección '{self.id}': 'start_s' debe ser menor que 'end_s'")
        return self

    @model_validator(mode="after")
    def _chords_are_inside_and_sorted(self) -> Self:
        times = [chord.t_s for chord in self.chords]
        if any(not self.start_s <= t < self.end_s for t in times):
            raise ValueError(f"sección '{self.id}': hay acordes fuera de la sección")
        if times != sorted(times):
            raise ValueError(f"sección '{self.id}': los acordes deben estar ordenados por 't_s'")
        return self

    @model_validator(mode="after")
    def _riff_has_events(self) -> Self:
        if self.riff is not None and not self.riff.events:
            raise ValueError(f"sección '{self.id}': un riff debe tener eventos (sin riff, null)")
        return self


class Key(_Strict):
    tonic: Annotated[str, Field(pattern=NOTE_PATTERN)]
    mode: Mode
    confidence: Confidence


class SourceStep(_Strict):
    """Un paso del pipeline que corrió: qué herramienta y qué versión."""

    step: Annotated[str, Field(min_length=1)]
    tool: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]


class BeatGrid(_Strict):
    """Instante (en segundos) de cada beat y del primer tiempo de cada compás."""

    beats_s: Annotated[list[Seconds], Field(min_length=2)]
    downbeats_s: list[Seconds] = Field(default_factory=list)

    @model_validator(mode="after")
    def _grid_is_increasing_and_downbeats_are_beats(self) -> Self:
        if any(a >= b for a, b in zip(self.beats_s, self.beats_s[1:], strict=False)):
            raise ValueError("'beats_s' debe ser estrictamente creciente")
        if any(a >= b for a, b in zip(self.downbeats_s, self.downbeats_s[1:], strict=False)):
            raise ValueError("'downbeats_s' debe ser estrictamente creciente")
        if any(not self._is_a_beat(downbeat) for downbeat in self.downbeats_s):
            raise ValueError("cada downbeat debe coincidir con un beat")
        return self

    def _is_a_beat(self, instant: float) -> bool:
        index = bisect.bisect_left(self.beats_s, instant)
        neighbours = self.beats_s[max(index - 1, 0) : index + 1]
        return any(abs(beat - instant) <= BEAT_TOLERANCE_S for beat in neighbours)


class SongChartContent(_Strict):
    instrument: Instrument
    key: Key | None = None
    bpm: Annotated[float, Field(gt=0, le=MAX_BPM)]
    bpm_confidence: Confidence | None = None
    time_signature: Annotated[str, Field(pattern=r"^[1-9][0-9]?/[1-9][0-9]?$")] = "4/4"
    capo: Annotated[int, Field(ge=0, le=MAX_CAPO_FRET)] = 0
    beat_grid: BeatGrid | None = None
    sections: Annotated[list[ChartSection], Field(min_length=1)]
    sources: list[SourceStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sections_are_unique_ordered_and_disjoint(self) -> Self:
        ids = [section.id for section in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("los ids de sección deben ser únicos")
        orders = [section.order for section in self.sections]
        if any(a >= b for a, b in zip(orders, orders[1:], strict=False)):
            raise ValueError("'order' debe ser estrictamente creciente en la lista de secciones")
        for previous, current in zip(self.sections, self.sections[1:], strict=False):
            if current.start_s < previous.end_s:
                raise ValueError(f"las secciones '{previous.id}' y '{current.id}' se solapan")
        return self

    @model_validator(mode="after")
    def _arpeggio_is_only_for_classical(self) -> Self:
        if self.instrument != "classical" and any(s.arpeggio for s in self.sections):
            raise ValueError("el arpegio p-i-m-a solo es válido para guitarra clásica")
        return self

    @model_validator(mode="after")
    def _riffs_fit_inside_their_section(self) -> Self:
        for section in self.sections:
            if section.riff is None:
                continue
            limit = section_length_beats(section, self.bpm, self.beat_grid) + RIFF_TOLERANCE_BEATS
            if any(event.t + event.dur > limit for event in section.riff.events):
                raise ValueError(f"sección '{section.id}': el riff se pasa del final de la sección")
        return self

    @model_validator(mode="after")
    def _beat_grid_is_inside_the_song(self) -> Self:
        end_of_song = self.sections[-1].end_s
        if self.beat_grid and self.beat_grid.beats_s[0] > end_of_song:
            raise ValueError("'beat_grid' empieza después del final de la última sección")
        return self


def seconds_to_beats(t_s: float, beat_grid: BeatGrid) -> float:
    """Posición en beats (el primer beat es 0): interpola entre beats y extrapola con el borde."""
    beats = beat_grid.beats_s
    index = min(max(bisect.bisect_right(beats, t_s) - 1, 0), len(beats) - 2)
    start, end = beats[index], beats[index + 1]
    return index + (t_s - start) / (end - start)


def section_length_beats(section: ChartSection, bpm: float, beat_grid: BeatGrid | None) -> float:
    """Duración de la sección en beats: por la grilla si hay, si no por el BPM del chart."""
    if beat_grid is None:
        return (section.end_s - section.start_s) * bpm / 60
    return seconds_to_beats(section.end_s, beat_grid) - seconds_to_beats(section.start_s, beat_grid)


def overall_confidence(content: SongChartContent) -> float | None:
    """Promedio simple de todas las confianzas del chart; `None` si no hay ninguna."""
    values: list[float] = [] if content.key is None else [content.key.confidence]
    if content.bpm_confidence is not None:
        values.append(content.bpm_confidence)
    for section in content.sections:
        values.extend(chord.confidence for chord in section.chords)
        values.extend(part.confidence for part in (section.strum, section.arpeggio) if part)
    return fmean(values) if values else None


def build_json_schema() -> dict[str, Any]:
    return SongChartContent.model_json_schema(schema_generator=NoFieldTitles)
