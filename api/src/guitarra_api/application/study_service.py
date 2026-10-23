"""Casos de uso de Estudio: consulta del currículum y registro de "Terminé"."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from guitarra_api.infra.db.models import Exercise, ExerciseCompletion, Lesson, Level
from guitarra_api.infra.db.repositories.curriculum import CurriculumRepository


class NotFoundError(Exception):
    """El recurso pedido no existe."""

    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(f"{resource} {resource_id} no existe")


@dataclass(frozen=True)
class ExerciseDetail:
    exercise: Exercise
    best_bpm: int | None


@dataclass(frozen=True)
class CompletionResult:
    completion: ExerciseCompletion
    best_bpm: int


class StudyService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = CurriculumRepository(session)

    def list_levels(self) -> list[Level]:
        return self._repo.list_levels()

    def list_lessons(self, level_id: int) -> list[Lesson]:
        if self._repo.get_level(level_id) is None:
            raise NotFoundError("Nivel", level_id)
        return self._repo.list_lessons(level_id)

    def get_lesson(self, lesson_id: int) -> tuple[Lesson, list[Exercise]]:
        lesson = self._repo.get_lesson(lesson_id)
        if lesson is None:
            raise NotFoundError("Lección", lesson_id)
        return lesson, self._repo.list_exercises(lesson_id)

    def get_exercise(self, exercise_id: int) -> ExerciseDetail:
        exercise = self._require_exercise(exercise_id)
        return ExerciseDetail(exercise, self._repo.best_bpm(exercise_id))

    def complete_exercise(
        self, exercise_id: int, bpm_achieved: int, instrument: str
    ) -> CompletionResult:
        self._require_exercise(exercise_id)
        completion = self._repo.add_completion(
            ExerciseCompletion(
                exercise_id=exercise_id,
                completed_at=dt.datetime.now(dt.UTC),
                bpm_achieved=bpm_achieved,
                instrument=instrument,
            )
        )
        self._session.commit()
        best = self._repo.best_bpm(exercise_id)
        return CompletionResult(completion, best if best is not None else bpm_achieved)

    def _require_exercise(self, exercise_id: int) -> Exercise:
        exercise = self._repo.get_exercise(exercise_id)
        if exercise is None:
            raise NotFoundError("Ejercicio", exercise_id)
        return exercise
