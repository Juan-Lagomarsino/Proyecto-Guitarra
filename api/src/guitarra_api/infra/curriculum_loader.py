"""Cargador idempotente del currículum (`curriculum/*.json`) a la base.

Uso: `python -m guitarra_api.infra.curriculum_loader` (lo corre `entrypoint.sh` después de alembic).
Formato de los archivos: ver `curriculum/README.md`.

Claves de upsert: nivel por `slug`, lección por (nivel, `slug`), ejercicio por `slug`; `position`
solo ordena. Nunca borra nada: se conservan las completions y lo que sale del JSON queda en la base.
"""

import json
import sys
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from guitarra_api.config import Settings
from guitarra_api.domain.notation import Notation

from .db.models import Exercise, Lesson, Level
from .db.session import get_sessionmaker

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=120)]
Instrument = Literal["classical", "electric"]
ExerciseType = Literal[
    "scale", "riff", "chords", "strumming", "arpeggio", "technique", "improvisation"
]
Category = Literal["warmup", "technique", "riff", "improvisation"]


class CurriculumError(Exception):
    """Error de contenido: el mensaje indica archivo y slug."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExerciseData(_Strict):
    slug: Slug
    title: Annotated[str, Field(min_length=1, max_length=200)]
    type: ExerciseType
    category: Category
    bpm_start: Annotated[int, Field(gt=0)]
    bpm_target: Annotated[int, Field(gt=0)]
    duration_min: Annotated[int, Field(gt=0)]
    description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]
    notation: Notation

    @model_validator(mode="after")
    def _tempos_are_consistent(self) -> Self:
        if self.bpm_target < self.bpm_start:
            raise ValueError("bpm_target no puede ser menor que bpm_start")
        if self.notation.bpm != self.bpm_start:
            raise ValueError("notation.bpm debe ser igual a bpm_start")
        return self


class LessonData(_Strict):
    slug: Slug
    position: Annotated[int, Field(ge=1)]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    content_md: str = ""
    exercises: list[ExerciseData]


class LevelData(_Strict):
    slug: Slug
    position: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: str = ""
    instrument: Instrument


class CurriculumFile(_Strict):
    level: LevelData
    lessons: list[LessonData]


class LevelContent(BaseModel):
    """Nivel ya validado, con sus lecciones; es lo que consume `sync_curriculum`."""

    slug: str
    position: int
    name: str
    description: str
    instrument: str
    lessons: list[LessonData]
    source: str


def _describe(error: ValidationError, path: Path) -> str:
    details = "; ".join(
        f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()
    )
    return f"{path.name}: {details}"


def _parse_file(path: Path) -> LevelContent:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CurriculumError(f"{path.name}: JSON inválido ({error})") from error
    _check_each_exercise(raw, path)
    try:
        data = CurriculumFile.model_validate(raw)
    except ValidationError as error:
        raise CurriculumError(_describe(error, path)) from error
    return LevelContent(**data.level.model_dump(), lessons=data.lessons, source=path.name)


def _check_each_exercise(raw: Any, path: Path) -> None:
    """Valida ejercicio por ejercicio para poder nombrar el slug que falla."""
    lessons = raw.get("lessons", []) if isinstance(raw, dict) else []
    for lesson in lessons:
        for exercise in lesson.get("exercises", []) if isinstance(lesson, dict) else []:
            try:
                ExerciseData.model_validate(exercise)
            except ValidationError as error:
                slug = exercise.get("slug", "?") if isinstance(exercise, dict) else "?"
                raise CurriculumError(f"{_describe(error, path)} (ejercicio '{slug}')") from error


def _check_unique(levels: list[LevelContent]) -> None:
    seen_positions: dict[int, str] = {}
    seen_slugs: dict[str, str] = {}
    seen_levels: dict[str, str] = {}
    for level in levels:
        if level.slug in seen_levels:
            raise CurriculumError(
                f"{level.source}: slug de nivel '{level.slug}' repetido "
                f"(ya está en {seen_levels[level.slug]})"
            )
        seen_levels[level.slug] = level.source
        if level.position in seen_positions:
            owner = seen_positions[level.position]
            raise CurriculumError(f"{level.source}: la posición {level.position} ya la usa {owner}")
        seen_positions[level.position] = level.source
        _check_lesson_positions(level)
        for lesson in level.lessons:
            for exercise in lesson.exercises:
                if exercise.slug in seen_slugs:
                    raise CurriculumError(
                        f"{level.source}: slug '{exercise.slug}' repetido "
                        f"(ya está en {seen_slugs[exercise.slug]})"
                    )
                seen_slugs[exercise.slug] = level.source


def _check_lesson_positions(level: LevelContent) -> None:
    positions = [lesson.position for lesson in level.lessons]
    if len(positions) != len(set(positions)):
        raise CurriculumError(f"{level.source}: posiciones de lección repetidas")
    slugs = [lesson.slug for lesson in level.lessons]
    if len(slugs) != len(set(slugs)):
        raise CurriculumError(f"{level.source}: slugs de lección repetidos")


def read_curriculum(directory: Path) -> list[LevelContent]:
    """Lee y valida todos los `*.json` de la carpeta; devuelve los niveles por posición."""
    if not directory.is_dir():
        raise CurriculumError(f"la carpeta del currículum no existe: {directory}")
    levels = [_parse_file(path) for path in sorted(directory.glob("*.json"))]
    _check_unique(levels)
    return sorted(levels, key=lambda level: level.position)


PARKED_POSITION_BASE = 1_000_000


def _park_positions(session: Session, rows: list[Level] | list[Lesson]) -> None:
    """Aparta las posiciones existentes para que reordenar no choque con el UNIQUE."""
    for row in rows:
        row.position = PARKED_POSITION_BASE + row.id
    session.flush()


def _upsert_level(session: Session, content: LevelContent) -> Level:
    level = session.scalar(select(Level).where(Level.slug == content.slug))
    if level is None:
        level = Level(slug=content.slug)
        session.add(level)
    level.position = content.position
    level.name = content.name
    level.description = content.description
    level.instrument = content.instrument
    session.flush()
    return level


def _upsert_lesson(session: Session, level: Level, data: LessonData) -> Lesson:
    lesson = session.scalar(
        select(Lesson).where(Lesson.level_id == level.id, Lesson.slug == data.slug)
    )
    if lesson is None:
        lesson = Lesson(level_id=level.id, slug=data.slug)
        session.add(lesson)
    lesson.position = data.position
    lesson.title = data.title
    lesson.content_md = data.content_md
    session.flush()
    return lesson


def _upsert_exercise(session: Session, lesson: Lesson, level: Level, data: ExerciseData) -> None:
    exercise = session.scalar(select(Exercise).where(Exercise.slug == data.slug))
    if exercise is None:
        exercise = Exercise(slug=data.slug)
        session.add(exercise)
    exercise.lesson_id = lesson.id
    exercise.title = data.title
    exercise.type = data.type
    exercise.category = data.category
    exercise.instrument = level.instrument
    exercise.notation = data.notation.model_dump(mode="json")
    exercise.bpm_start = data.bpm_start
    exercise.bpm_target = data.bpm_target
    exercise.duration_min = data.duration_min
    exercise.description = data.description
    session.flush()


def sync_curriculum(session: Session, levels: list[LevelContent]) -> None:
    """Upsert de todo el contenido. No hace commit: lo decide quien llama."""
    _park_positions(session, list(session.scalars(select(Level))))
    for content in levels:
        level = _upsert_level(session, content)
        _park_positions(
            session, list(session.scalars(select(Lesson).where(Lesson.level_id == level.id)))
        )
        for lesson_data in content.lessons:
            lesson = _upsert_lesson(session, level, lesson_data)
            for exercise_data in lesson_data.exercises:
                _upsert_exercise(session, lesson, level, exercise_data)


def main() -> int:
    directory = Settings().guitar_curriculum_dir
    try:
        levels = read_curriculum(directory)
    except CurriculumError as error:
        print(f"Error en el currículum: {error}", file=sys.stderr)
        return 1
    with get_sessionmaker()() as session:
        sync_curriculum(session, levels)
        session.commit()
    total = sum(len(lesson.exercises) for level in levels for lesson in level.lessons)
    print(f"Currículum cargado: {len(levels)} nivel(es), {total} ejercicio(s) desde {directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
