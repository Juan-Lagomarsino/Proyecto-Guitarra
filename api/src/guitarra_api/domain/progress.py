"""Días de práctica y racha. Funciones puras: sin DB, sin reloj, sin framework.

Semántica de la racha:
- Un día cuenta como practicado si tiene al menos una completion (en la zona local).
- Un día excluido sin práctica no corta la racha ni suma; si se practica, suma.
- La racha actual sigue viva si hoy todavía no se practicó.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

_ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class ProgressSummary:
    practiced_days: tuple[date, ...]
    completions_per_day: dict[date, int]
    current_streak: int
    max_streak: int
    total_days: int


def compute_progress(
    completions: Iterable[datetime],
    timezone: ZoneInfo | str,
    excluded_weekdays: frozenset[int] | set[int],
    today: date,
) -> ProgressSummary:
    """Calcula días practicados y rachas.

    `excluded_weekdays` usa enteros 0-6 con 0 = lunes (como `date.weekday()`).
    `today` es la fecha local ya resuelta por quien llama.
    """
    zone = ZoneInfo(timezone) if isinstance(timezone, str) else timezone
    excluded = _validate_weekdays(excluded_weekdays)
    per_day = Counter(_local_day(moment, zone) for moment in completions)
    practiced = tuple(sorted(per_day))
    return ProgressSummary(
        practiced_days=practiced,
        completions_per_day=dict(sorted(per_day.items())),
        current_streak=_current_streak(set(practiced), excluded, today),
        max_streak=_max_streak(practiced, excluded),
        total_days=len(practiced),
    )


def _validate_weekdays(weekdays: Iterable[int]) -> frozenset[int]:
    result = frozenset(weekdays)
    if any(not 0 <= day <= 6 for day in result):
        raise ValueError("Los días excluidos deben estar entre 0 y 6 (0 = lunes)")
    return result


def _local_day(moment: datetime, zone: ZoneInfo) -> date:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("La completion debe traer zona horaria (datetime naive no permitido)")
    return moment.astimezone(zone).date()


def _current_streak(practiced: set[date], excluded: frozenset[int], today: date) -> int:
    day = today if today in practiced else today - _ONE_DAY
    if not practiced:
        return 0
    streak = 0
    earliest = min(practiced)
    while day >= earliest:
        if day in practiced:
            streak += 1
        elif day.weekday() not in excluded:
            break
        day -= _ONE_DAY
    return streak


def _max_streak(practiced: tuple[date, ...], excluded: frozenset[int]) -> int:
    best = current = 0
    previous: date | None = None
    for day in practiced:
        if previous is not None and _has_gap(previous, day, excluded):
            current = 0
        current += 1
        best = max(best, current)
        previous = day
    return best


def _has_gap(previous: date, day: date, excluded: frozenset[int]) -> bool:
    """True si entre dos días practicados hay algún día no excluido sin práctica."""
    between = previous + _ONE_DAY
    while between < day:
        if between.weekday() not in excluded:
            return True
        between += _ONE_DAY
    return False
