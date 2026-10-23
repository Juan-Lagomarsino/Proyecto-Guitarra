from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Exercise, ExerciseCompletion, Lesson, Level


class CurriculumRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_exercise(self, exercise: Exercise) -> Exercise:
        self._session.add(exercise)
        self._session.flush()
        return exercise

    def get_exercise_by_slug(self, slug: str) -> Exercise | None:
        return self._session.scalar(select(Exercise).where(Exercise.slug == slug))

    def list_exercises(self, lesson_id: int) -> list[Exercise]:
        query = select(Exercise).where(Exercise.lesson_id == lesson_id).order_by(Exercise.id)
        return list(self._session.scalars(query))

    def add_completion(self, completion: ExerciseCompletion) -> ExerciseCompletion:
        self._session.add(completion)
        self._session.flush()
        return completion

    def list_completions(self, exercise_id: int) -> list[ExerciseCompletion]:
        query = (
            select(ExerciseCompletion)
            .where(ExerciseCompletion.exercise_id == exercise_id)
            .order_by(ExerciseCompletion.completed_at)
        )
        return list(self._session.scalars(query))

    def list_levels(self) -> list[Level]:
        return list(self._session.scalars(select(Level).order_by(Level.position)))

    def get_level(self, level_id: int) -> Level | None:
        return self._session.get(Level, level_id)

    def list_lessons(self, level_id: int) -> list[Lesson]:
        query = select(Lesson).where(Lesson.level_id == level_id).order_by(Lesson.position)
        return list(self._session.scalars(query))

    def get_lesson(self, lesson_id: int) -> Lesson | None:
        return self._session.get(Lesson, lesson_id)

    def get_exercise(self, exercise_id: int) -> Exercise | None:
        return self._session.get(Exercise, exercise_id)

    def best_bpm(self, exercise_id: int) -> int | None:
        query = select(func.max(ExerciseCompletion.bpm_achieved)).where(
            ExerciseCompletion.exercise_id == exercise_id
        )
        return self._session.scalar(query)
