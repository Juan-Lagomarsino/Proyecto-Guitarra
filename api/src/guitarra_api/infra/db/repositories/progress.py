"""Lecturas de la DB que alimentan el dominio de progreso y el generador de sesión."""

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Exercise, ExerciseCompletion, Lesson, Level, PracticeSession, SongSection


class ProgressRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def completion_times(self) -> list[dt.datetime]:
        return list(self._session.scalars(select(ExerciseCompletion.completed_at)))

    def completed_exercise_ids_between(self, start: dt.datetime, end: dt.datetime) -> set[int]:
        """Ejercicios con alguna completion en start <= completed_at < end."""
        query = select(ExerciseCompletion.exercise_id).where(
            ExerciseCompletion.completed_at >= start, ExerciseCompletion.completed_at < end
        )
        return set(self._session.scalars(query))

    def best_bpm_by_exercise(self) -> dict[int, int]:
        query = select(
            ExerciseCompletion.exercise_id, func.max(ExerciseCompletion.bpm_achieved)
        ).group_by(ExerciseCompletion.exercise_id)
        return {row[0]: row[1] or 0 for row in self._session.execute(query)}

    def level_progress(self) -> list[tuple[Level, int, int]]:
        """(nivel, ejercicios completados al menos una vez, total de ejercicios)."""
        done = (
            select(ExerciseCompletion.exercise_id)
            .group_by(ExerciseCompletion.exercise_id)
            .subquery()
        )
        query = (
            select(Level, func.count(done.c.exercise_id), func.count(Exercise.id))
            .outerjoin(Lesson, Lesson.level_id == Level.id)
            .outerjoin(Exercise, Exercise.lesson_id == Lesson.id)
            .outerjoin(done, done.c.exercise_id == Exercise.id)
            .group_by(Level.id)
            .order_by(Level.position)
        )
        return [(row[0], row[1], row[2]) for row in self._session.execute(query)]

    def songs_in_progress(self) -> int:
        """Canciones en curso: las que tienen al menos un ejercicio creado desde una sección.

        No exige que alguno se haya completado: crear la práctica ya cuenta como empezar.
        """
        query = select(func.count(func.distinct(SongSection.song_id))).join(
            Exercise, Exercise.song_section_id == SongSection.id
        )
        return self._session.scalar(query) or 0

    def exercises_with_level_position(self) -> list[tuple[Exercise, int]]:
        query = (
            select(Exercise, Level.position)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .join(Level, Lesson.level_id == Level.id)
            .order_by(Exercise.id)
        )
        return [(row[0], row[1]) for row in self._session.execute(query)]

    def exercises_by_ids(self, ids: list[int]) -> dict[int, Exercise]:
        if not ids:
            return {}
        query = select(Exercise).where(Exercise.id.in_(ids))
        return {exercise.id: exercise for exercise in self._session.scalars(query)}

    def get_practice_session(self, day: dt.date) -> PracticeSession | None:
        return self._session.scalar(select(PracticeSession).where(PracticeSession.date == day))

    def save_practice_session(self, practice: PracticeSession) -> PracticeSession:
        self._session.add(practice)
        self._session.commit()
        return practice

    def rollback(self) -> None:
        self._session.rollback()
