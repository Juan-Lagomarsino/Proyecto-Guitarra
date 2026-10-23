"""Casos de uso de la sesión del día: crearla una vez por día local y regenerarla."""

import datetime as dt
import secrets
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock, local_today
from guitarra_api.domain.session_planner import ExerciseInfo, SessionPlan, build_session
from guitarra_api.infra.db.models import PracticeSession
from guitarra_api.infra.db.repositories.progress import ProgressRepository
from guitarra_api.infra.db.repositories.settings import SettingsRepository

_MAX_SEED = 2**31 - 1
_REGENERATE_ATTEMPTS = 10


@dataclass(frozen=True)
class SessionExercise:
    id: int
    title: str
    category: str
    minutes: int
    duration_min: int
    bpm_target: int | None
    completed_today: bool


@dataclass(frozen=True)
class SessionBlockView:
    category: str
    minutes: int
    exercises: list[SessionExercise]


@dataclass(frozen=True)
class TodaySession:
    date: dt.date
    seed: int
    status: str
    total_minutes: int
    blocks: list[SessionBlockView]


class SessionService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._repo = ProgressRepository(session)
        self._settings = SettingsRepository(session)
        self._clock = clock
        self._timezone: str | None = None

    def today(self) -> TodaySession:
        return self._view(self._get_or_create_today())

    def regenerate(self) -> TodaySession:
        practice = self._get_or_create_today()
        seed, planned = practice.seed, practice.planned
        # Si tras _REGENERATE_ATTEMPTS el plan sigue igual (poco material), se acepta la nueva
        # semilla con el mismo plan: no hay con qué variar.
        for _ in range(_REGENERATE_ATTEMPTS):
            seed = _new_seed(exclude=practice.seed)
            planned = self._plan(seed)
            if planned != practice.planned:
                break
        practice.seed, practice.planned = seed, planned
        return self._view(self._repo.save_practice_session(practice))

    def _get_or_create_today(self) -> PracticeSession:
        day = local_today(self._clock, self._timezone_name())
        practice = self._repo.get_practice_session(day)
        if practice is not None:
            return practice
        seed = _new_seed()
        new = PracticeSession(date=day, seed=seed, status="planned", planned=self._plan(seed))
        try:
            return self._repo.save_practice_session(new)
        except IntegrityError:
            # Otro request creó la sesión de hoy entre la lectura y el insert: usamos la suya.
            self._repo.rollback()
            existing = self._repo.get_practice_session(day)
            if existing is None:
                raise
            return existing

    def _timezone_name(self) -> str:
        if self._timezone is None:
            self._timezone = self._settings.get().timezone
        return self._timezone

    def _plan(self, seed: int) -> list[dict[str, Any]]:
        infos = [
            ExerciseInfo(
                id=str(exercise.id),
                level_order=position,
                type=exercise.type,
                category=exercise.category,
                duration_min=exercise.duration_min,
                bpm_target=exercise.bpm_target,
            )
            for exercise, position in self._repo.exercises_with_level_position()
        ]
        history = {str(key): bpm for key, bpm in self._repo.best_bpm_by_exercise().items()}
        return _serialize(build_session(infos, history, seed))

    def _view(self, practice: PracticeSession) -> TodaySession:
        exercises = self._repo.exercises_by_ids([item["exercise_id"] for item in practice.planned])
        done = self._completed_on(practice.date)
        grouped: dict[str, list[SessionExercise]] = {}
        for item in practice.planned:
            exercise = exercises.get(item["exercise_id"])
            if exercise is None:  # ejercicio borrado después de armar la sesión
                continue
            grouped.setdefault(item["block"], []).append(
                SessionExercise(
                    id=exercise.id,
                    title=exercise.title,
                    category=exercise.category,
                    minutes=item["minutes"],
                    duration_min=exercise.duration_min,
                    bpm_target=exercise.bpm_target,
                    completed_today=exercise.id in done,
                )
            )
        blocks = [
            SessionBlockView(category, sum(e.minutes for e in items), items)
            for category, items in grouped.items()
        ]
        total = sum(block.minutes for block in blocks)
        return TodaySession(practice.date, practice.seed, practice.status, total, blocks)

    def _completed_on(self, day: dt.date) -> set[int]:
        zone = ZoneInfo(self._timezone_name())
        start = dt.datetime.combine(day, dt.time.min, tzinfo=zone)
        end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min, tzinfo=zone)
        return self._repo.completed_exercise_ids_between(start, end)


def _new_seed(exclude: int | None = None) -> int:
    seed = secrets.randbelow(_MAX_SEED)
    while seed == exclude:
        seed = secrets.randbelow(_MAX_SEED)
    return seed


def _serialize(plan: SessionPlan) -> list[dict[str, Any]]:
    return [
        {"block": block.category, "exercise_id": int(item.exercise.id), "minutes": item.minutes}
        for block in plan.blocks
        for item in block.exercises
    ]
