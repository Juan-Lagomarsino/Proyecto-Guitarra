from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Exercise, ExerciseCompletion


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
