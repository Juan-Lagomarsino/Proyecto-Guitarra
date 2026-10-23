"""Reloj inyectable y resolución del "hoy" local."""

import datetime as dt
from collections.abc import Callable
from zoneinfo import ZoneInfo

Clock = Callable[[], dt.datetime]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def local_today(clock: Clock, timezone: str) -> dt.date:
    return clock().astimezone(ZoneInfo(timezone)).date()
