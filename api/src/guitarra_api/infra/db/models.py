"""Modelos SQLAlchemy de la Fase 1. Timestamps en UTC; la fecha local de práctica es una `date`."""

import datetime as dt
from typing import Any

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from guitarra_api.domain.app_settings import INSTRUMENTS

from .base import Base

EXERCISE_TYPES = ("scale", "riff", "chords", "strumming", "arpeggio", "technique", "improvisation")
CATEGORIES = ("warmup", "technique", "riff", "improvisation")
SESSION_STATUSES = ("planned", "in_progress", "completed", "skipped")
DEFAULT_TUNING = ["E2", "A2", "D3", "G3", "B3", "E4"]


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class Level(Base):
    __tablename__ = "levels"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_levels_slug"),
        UniqueConstraint("position", name="uq_levels_position"),
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    instrument: Mapped[str] = mapped_column(String(20))

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="level", order_by="Lesson.position"
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("level_id", "slug", name="uq_lessons_level_slug"),
        UniqueConstraint("level_id", "position", name="uq_lessons_level_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    level_id: Mapped[int] = mapped_column(ForeignKey("levels.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(120))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    content_md: Mapped[str] = mapped_column(Text, default="")

    level: Mapped[Level] = relationship(back_populates="lessons")
    exercises: Mapped[list["Exercise"]] = relationship(back_populates="lesson")


class Exercise(Base):
    """Pertenece a una lección. `song_section_id` llega en la Fase 2 con su migración."""

    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(_in_list("type", EXERCISE_TYPES), name="type_valid"),
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
        CheckConstraint(_in_list("category", CATEGORIES), name="category_valid"),
        CheckConstraint("bpm_start > 0", name="bpm_start_positive"),
        CheckConstraint("bpm_target > 0", name="bpm_target_positive"),
        CheckConstraint("bpm_target >= bpm_start", name="bpm_target_gte_start"),
        CheckConstraint("duration_min > 0", name="duration_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    instrument: Mapped[str] = mapped_column(String(20))
    notation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    bpm_start: Mapped[int | None] = mapped_column(Integer)
    bpm_target: Mapped[int | None] = mapped_column(Integer)
    duration_min: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)

    lesson: Mapped[Lesson] = relationship(back_populates="exercises")


class ExerciseCompletion(Base):
    __tablename__ = "exercise_completions"
    __table_args__ = (
        CheckConstraint("bpm_achieved > 0", name="bpm_achieved_positive"),
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )
    completed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    bpm_achieved: Mapped[int | None] = mapped_column(Integer)
    instrument: Mapped[str] = mapped_column(String(20))


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (CheckConstraint(_in_list("status", SESSION_STATUSES), name="status_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, unique=True)  # fecha local (Settings.timezone)
    planned: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{exercise_id, minutes}]
    status: Mapped[str] = mapped_column(String(20), default="planned")
    seed: Mapped[int] = mapped_column(Integer)


class Settings(Base):
    """Fila única: `id` fijo en 1 forzado con CHECK (id = 1)."""

    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint(
            _in_list("default_instrument", INSTRUMENTS), name="default_instrument_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    timezone: Mapped[str] = mapped_column(
        String(64), default="America/Montevideo", server_default="America/Montevideo"
    )
    theme_tokens: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    fonts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    default_instrument: Mapped[str] = mapped_column(
        String(20), default="electric", server_default="electric"
    )
    tuning: Mapped[list[str]] = mapped_column(
        JSONB,
        default=lambda: list(DEFAULT_TUNING),
        server_default=text("""'["E2","A2","D3","G3","B3","E4"]'::jsonb"""),
    )


class ReminderRules(Base):
    """Fila única: `id` fijo en 1 forzado con CHECK (id = 1). Días 0-6, con 0 = lunes."""

    __tablename__ = "reminder_rules"
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("excluded_weekdays <@ ARRAY[0,1,2,3,4,5,6]", name="weekdays_range"),
        CheckConstraint("inactivity_threshold_days > 0", name="threshold_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False, default=1)
    excluded_weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, server_default=text("'{}'")
    )
    inactivity_threshold_days: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    preferred_window: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # {start, end} HH:MM
