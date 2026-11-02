"""Modelos SQLAlchemy (Fase 1: estudio y progreso; Fase 2: canciones y cola de análisis).

Timestamps en UTC; la fecha local de práctica es una `date`.
"""

import datetime as dt
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from guitarra_api.domain.app_settings import INSTRUMENTS
from guitarra_api.domain.song_chart import SongChartContent

from .base import Base

EXERCISE_TYPES = ("scale", "riff", "chords", "strumming", "arpeggio", "technique", "improvisation")
CATEGORIES = ("warmup", "technique", "riff", "improvisation")
SESSION_STATUSES = ("planned", "in_progress", "completed", "skipped")
SONG_SOURCES = ("youtube", "spotify", "search")
ANALYSIS_STATUSES = ("queued", "processing", "ready", "error")
CHART_ORIGINS = ("auto", "cifraclub", "user")
AUDIO_ASSET_KINDS = ("original", "no_guitar", "stem")
JOB_STATUSES = ("queued", "running", "done", "error")
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
    """Pertenece a una lección **o** a una sección de canción (exactamente una de las dos)."""

    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint(_in_list("type", EXERCISE_TYPES), name="type_valid"),
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
        CheckConstraint(_in_list("category", CATEGORIES), name="category_valid"),
        CheckConstraint("bpm_start > 0", name="bpm_start_positive"),
        CheckConstraint("bpm_target > 0", name="bpm_target_positive"),
        CheckConstraint("bpm_target >= bpm_start", name="bpm_target_gte_start"),
        CheckConstraint("duration_min > 0", name="duration_positive"),
        CheckConstraint(
            "(lesson_id IS NULL) <> (song_section_id IS NULL)", name="lesson_xor_song_section"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    song_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("song_sections.id", ondelete="CASCADE"), index=True
    )
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

    lesson: Mapped[Lesson | None] = relationship(back_populates="exercises")


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


class Song(Base):
    """Una por canción, independiente del instrumento."""

    __tablename__ = "songs"
    __table_args__ = (
        CheckConstraint(_in_list("source", SONG_SOURCES), name="source_valid"),
        CheckConstraint(_in_list("analysis_status", ANALYSIS_STATUSES), name="status_valid"),
        CheckConstraint("duration_s IS NULL OR duration_s > 0", name="duration_positive"),
        CheckConstraint("bpm IS NULL OR bpm > 0", name="bpm_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(300))
    artist: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(20))
    url: Mapped[str | None] = mapped_column(Text)
    youtube_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    spotify_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    duration_s: Mapped[float | None] = mapped_column(Float)
    bpm: Mapped[float | None] = mapped_column(Float)
    key: Mapped[str | None] = mapped_column(String(20))  # tonalidad, p. ej. "A minor"
    year: Mapped[int | None] = mapped_column(Integer)
    cifra_text: Mapped[str | None] = mapped_column(Text)  # pegada a mano (ADR 0012)
    cifra_url: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str] = mapped_column(
        String(20), default="queued", server_default="queued"
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sections: Mapped[list["SongSection"]] = relationship(
        back_populates="song", order_by="SongSection.position"
    )
    audio_assets: Mapped[list["AudioAsset"]] = relationship(
        order_by="AudioAsset.kind", passive_deletes=True
    )


class SongSection(Base):
    """Sección con tiempos. `slug` es el id estable de la sección dentro del `SongChart`."""

    __tablename__ = "song_sections"
    __table_args__ = (
        UniqueConstraint("song_id", "position", name="uq_song_sections_song_position"),
        UniqueConstraint("song_id", "slug", name="uq_song_sections_song_slug"),
        CheckConstraint("start_s >= 0 AND start_s < end_s", name="times_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(120))
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    position: Mapped[int] = mapped_column(Integer)
    # Desapareció en un reanálisis pero tiene ejercicios: se conserva marcada.
    stale: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    song: Mapped[Song] = relationship(back_populates="sections")


class SongChart(Base):
    """Versionado por canción e instrumento. `content` es un `SongChartContent` validado."""

    __tablename__ = "song_charts"
    __table_args__ = (
        UniqueConstraint("song_id", "instrument", "version", name="uq_song_charts_version"),
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
        CheckConstraint(_in_list("origin", CHART_ORIGINS), name="origin_valid"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="confidence_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    instrument: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    origin: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Versión de usuario descartada al volver a la automática: se conserva para el historial.
    discarded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("content")
    def _validate_content(self, _key: str, value: dict[str, Any]) -> dict[str, Any]:
        """Rechaza al guardar todo lo que no cumpla el esquema del dominio."""
        return SongChartContent.model_validate(value).model_dump(mode="json")


class AudioAsset(Base):
    __tablename__ = "audio_assets"
    __table_args__ = (
        CheckConstraint(_in_list("kind", AUDIO_ASSET_KINDS), name="kind_valid"),
        UniqueConstraint("song_id", "kind", name="uq_audio_assets_song_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(10))


class AnalysisJob(Base):
    """Cola que consume el worker: se toma con lease y se reintenta hasta `max_attempts`."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(_in_list("status", JOB_STATUSES), name="status_valid"),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        Index("ix_analysis_jobs_status_lease_until", "status", "lease_until"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    song_id: Mapped[int] = mapped_column(ForeignKey("songs.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(30), default="analyze", server_default="analyze")
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claimed_by: Mapped[str | None] = mapped_column(String(120))
    lease_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    current_step: Mapped[str | None] = mapped_column(String(60))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Correction(Base):
    """Historial de ediciones del usuario sobre un chart (insumo para el aprendizaje)."""

    __tablename__ = "corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    song_chart_id: Mapped[int] = mapped_column(
        ForeignKey("song_charts.id", ondelete="CASCADE"), index=True
    )
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChordShapePreference(Base):
    """Formas de acorde que el usuario prefiere en un instrumento: `{acorde: {forma: peso}}`."""

    __tablename__ = "chord_shape_preferences"
    __table_args__ = (
        CheckConstraint(_in_list("instrument", INSTRUMENTS), name="instrument_valid"),
    )

    instrument: Mapped[str] = mapped_column(String(20), primary_key=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
