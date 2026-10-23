import datetime as dt

from pydantic import BaseModel


class LevelProgressOut(BaseModel):
    level_id: int
    slug: str
    position: int
    name: str
    completed: int
    total: int


class SummaryOut(BaseModel):
    current_streak: int
    max_streak: int
    practiced_days: int
    levels: list[LevelProgressOut]


class CalendarDayOut(BaseModel):
    date: dt.date
    count: int


class CalendarOut(BaseModel):
    days: list[CalendarDayOut]


class SessionExerciseOut(BaseModel):
    id: int
    title: str
    category: str
    minutes: int
    duration_min: int
    bpm_target: int | None
    completed_today: bool


class SessionBlockOut(BaseModel):
    category: str
    minutes: int
    exercises: list[SessionExerciseOut]


class TodaySessionOut(BaseModel):
    date: dt.date
    seed: int
    status: str
    total_minutes: int
    blocks: list[SessionBlockOut]
