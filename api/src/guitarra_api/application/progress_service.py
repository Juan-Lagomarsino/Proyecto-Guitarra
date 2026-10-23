"""Casos de uso de Progreso: resumen, calendario y avance por nivel."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy.orm import Session

from guitarra_api.application.clock import Clock, local_today
from guitarra_api.domain.progress import ProgressSummary, compute_progress
from guitarra_api.infra.db.repositories.progress import ProgressRepository
from guitarra_api.infra.db.repositories.reminder_rules import ReminderRulesRepository
from guitarra_api.infra.db.repositories.settings import SettingsRepository


class InvalidRangeError(Exception):
    def __init__(self) -> None:
        super().__init__("`from` no puede ser posterior a `to`")


@dataclass(frozen=True)
class LevelProgress:
    level_id: int
    slug: str
    position: int
    name: str
    completed: int
    total: int


@dataclass(frozen=True)
class Summary:
    current_streak: int
    max_streak: int
    practiced_days: int
    levels: list[LevelProgress]


class ProgressService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self._repo = ProgressRepository(session)
        self._settings = SettingsRepository(session)
        self._rules = ReminderRulesRepository(session)
        self._clock = clock

    def summary(self) -> Summary:
        progress = self._compute()
        levels = [
            LevelProgress(level.id, level.slug, level.position, level.name, done, total)
            for level, done, total in self._repo.level_progress()
        ]
        return Summary(progress.current_streak, progress.max_streak, progress.total_days, levels)

    def calendar(self, start: dt.date, end: dt.date) -> list[tuple[dt.date, int]]:
        if start > end:
            raise InvalidRangeError
        per_day = self._compute().completions_per_day
        return [(day, count) for day, count in per_day.items() if start <= day <= end]

    def _compute(self) -> ProgressSummary:
        timezone = self._settings.get().timezone
        return compute_progress(
            self._repo.completion_times(),
            timezone,
            frozenset(self._rules.get().excluded_weekdays),
            local_today(self._clock, timezone),
        )
