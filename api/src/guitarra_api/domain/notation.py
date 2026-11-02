"""Formato único de notación (fuente de verdad del JSON Schema y de los tipos TS).

`t` y `dur` se expresan en tiempos (beats). Ver ADR 0003.
"""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import core_schema

NUM_STRINGS = 6
MAX_FRET = 24

NOTE_PATTERN = r"^[A-G][#b]?$"
NOTE_WITH_OCTAVE_PATTERN = r"^[A-G][#b]?[0-9]$"
TIME_SIGNATURE_PATTERN = r"^[1-9][0-9]?/[1-9][0-9]?$"
STRUM_PATTERN = r"^[DU-]+$"
STANDARD_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]

Technique = Literal["h", "p", "/", "\\", "b", "r", "~", "pm", "x"]
StringNumber = Annotated[int, Field(ge=1, le=NUM_STRINGS)]
Fret = Annotated[int, Field(ge=0, le=MAX_FRET)]
Beats = Annotated[float, Field(ge=0)]
NoteWithOctave = Annotated[str, Field(pattern=NOTE_WITH_OCTAVE_PATTERN)]
ChordName = Annotated[str, Field(min_length=1)]
ChordShape = Annotated[
    list[Fret | Literal["x"]],
    Field(min_length=NUM_STRINGS, max_length=NUM_STRINGS),
]
StrumPattern = Annotated[str, Field(min_length=1, pattern=STRUM_PATTERN)]
StrumAccents = list[Annotated[int, Field(ge=0)]]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoteEvent(_Strict):
    t: Beats
    dur: Annotated[float, Field(gt=0)]
    string: StringNumber
    fret: Fret
    technique: Technique | None = None
    bend: Annotated[float, Field(gt=0)] | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] | None = None

    @model_validator(mode="after")
    def _bend_goes_with_bend_technique(self) -> Self:
        if self.technique == "b" and self.bend is None:
            raise ValueError("la técnica 'b' requiere el campo 'bend'")
        if self.technique != "b" and self.bend is not None:
            raise ValueError("'bend' solo es válido con la técnica 'b'")
        return self


class Barre(_Strict):
    """Cejilla: traste y rango de cuerdas, de la más grave (6) a la más aguda (1)."""

    fret: Annotated[int, Field(ge=1, le=MAX_FRET)]
    from_string: StringNumber
    to_string: StringNumber

    @model_validator(mode="after")
    def _from_is_lower_than_to(self) -> Self:
        if self.from_string <= self.to_string:
            raise ValueError("'from_string' debe ser una cuerda más grave que 'to_string'")
        return self


class Chord(_Strict):
    t: Beats
    name: ChordName
    shape: ChordShape
    barre: Barre | None = None


def ensure_accents_inside_pattern(pattern: str, accent: list[int]) -> None:
    if any(index >= len(pattern) for index in accent):
        raise ValueError("'accent' tiene índices fuera del patrón")


class Strum(_Strict):
    t: Beats
    pattern: StrumPattern
    accent: StrumAccents = Field(default_factory=list)

    @model_validator(mode="after")
    def _accents_point_inside_pattern(self) -> Self:
        ensure_accents_inside_pattern(self.pattern, self.accent)
        return self


class Notation(_Strict):
    tuning: Annotated[
        list[NoteWithOctave],
        Field(min_length=NUM_STRINGS, max_length=NUM_STRINGS),
    ] = Field(default_factory=lambda: list(STANDARD_TUNING))
    bpm: Annotated[float, Field(gt=0, le=400)]
    time_signature: Annotated[str, Field(pattern=TIME_SIGNATURE_PATTERN)] = "4/4"
    events: list[NoteEvent] = Field(default_factory=list)
    chords: list[Chord] = Field(default_factory=list)
    strum: list[Strum] = Field(default_factory=list)
    tonic: Annotated[str, Field(pattern=NOTE_PATTERN)] | None = None


class NoFieldTitles(GenerateJsonSchema):
    """Sin títulos autogenerados por campo: evita tipos TS con nombres como `String`."""

    def field_title_should_be_set(self, schema: core_schema.CoreSchema) -> bool:
        return False


def build_json_schema() -> dict[str, Any]:
    return Notation.model_json_schema(schema_generator=NoFieldTitles)
