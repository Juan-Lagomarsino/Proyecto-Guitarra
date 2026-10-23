import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    position: int
    name: str
    description: str
    instrument: str


class LessonSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level_id: int
    slug: str
    position: int
    title: str


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lesson_id: int | None = Field(description="null en los ejercicios de canción")
    song_section_id: int | None = Field(description="null en los ejercicios de una lección")
    slug: str
    title: str
    type: str
    instrument: str
    category: str
    bpm_start: int | None
    bpm_target: int | None
    duration_min: int
    description: str | None
    notation: dict[str, Any]


class ExerciseDetailOut(ExerciseOut):
    best_bpm: int | None = Field(description="Mejor BPM logrado; null si nunca se completó")


class LessonOut(LessonSummaryOut):
    content_md: str
    exercises: list[ExerciseOut]


class CompletionIn(BaseModel):
    bpm_logrado: int = Field(gt=0, description="BPM logrado, entero positivo")
    instrumento: Literal["classical", "electric"]


class CompletionOut(BaseModel):
    id: int
    exercise_id: int
    completed_at: dt.datetime = Field(description="Instante UTC generado por el servidor")
    bpm_logrado: int
    instrumento: str
    best_bpm: int
