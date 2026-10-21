"""Esquema inicial de la Fase 1.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EXERCISE_TYPES = "'scale', 'riff', 'chords', 'strumming', 'arpeggio', 'technique', 'improvisation'"
CATEGORIES = "'warmup', 'technique', 'riff', 'improvisation'"
INSTRUMENTS = "'classical', 'electric'"
SESSION_STATUSES = "'planned', 'in_progress', 'completed', 'skipped'"


def upgrade() -> None:
    op.create_table(
        "levels",
        sa.Column("id", sa.Integer()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_levels")),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.UniqueConstraint("slug", name=op.f("uq_levels_slug")),
        sa.UniqueConstraint("position", name=op.f("uq_levels_position")),
        sa.CheckConstraint(
            f"instrument IN ({INSTRUMENTS})", name=op.f("ck_levels_instrument_valid")
        ),
    )
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lessons")),
        sa.Column(
            "level_id",
            sa.Integer(),
            sa.ForeignKey("levels.id", ondelete="CASCADE", name=op.f("fk_lessons_level_id_levels")),
            nullable=False,
        ),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.UniqueConstraint("level_id", "slug", name=op.f("uq_lessons_level_slug")),
        sa.UniqueConstraint("level_id", "position", name=op.f("uq_lessons_level_position")),
    )
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercises")),
        sa.Column(
            "lesson_id",
            sa.Integer(),
            sa.ForeignKey(
                "lessons.id", ondelete="CASCADE", name=op.f("fk_exercises_lesson_id_lessons")
            ),
            nullable=False,
        ),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("notation", postgresql.JSONB(), nullable=False),
        sa.Column("bpm_start", sa.Integer()),
        sa.Column("bpm_target", sa.Integer()),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.UniqueConstraint("slug", name=op.f("uq_exercises_slug")),
        sa.CheckConstraint(f"type IN ({EXERCISE_TYPES})", name=op.f("ck_exercises_type_valid")),
        sa.CheckConstraint(
            f"instrument IN ({INSTRUMENTS})", name=op.f("ck_exercises_instrument_valid")
        ),
        sa.CheckConstraint(f"category IN ({CATEGORIES})", name=op.f("ck_exercises_category_valid")),
        sa.CheckConstraint("bpm_start > 0", name=op.f("ck_exercises_bpm_start_positive")),
        sa.CheckConstraint("bpm_target > 0", name=op.f("ck_exercises_bpm_target_positive")),
        sa.CheckConstraint(
            "bpm_target >= bpm_start", name=op.f("ck_exercises_bpm_target_gte_start")
        ),
        sa.CheckConstraint("duration_min > 0", name=op.f("ck_exercises_duration_positive")),
    )
    op.create_table(
        "exercise_completions",
        sa.Column("id", sa.Integer()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercise_completions")),
        sa.Column(
            "exercise_id",
            sa.Integer(),
            sa.ForeignKey(
                "exercises.id",
                ondelete="CASCADE",
                name=op.f("fk_exercise_completions_exercise_id_exercises"),
            ),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("bpm_achieved", sa.Integer()),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.CheckConstraint(
            "bpm_achieved > 0", name=op.f("ck_exercise_completions_bpm_achieved_positive")
        ),
        sa.CheckConstraint(
            f"instrument IN ({INSTRUMENTS})",
            name=op.f("ck_exercise_completions_instrument_valid"),
        ),
    )
    op.create_index(
        op.f("ix_exercise_completions_exercise_id"), "exercise_completions", ["exercise_id"]
    )
    op.create_table(
        "practice_sessions",
        sa.Column("id", sa.Integer()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_practice_sessions")),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("planned", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.UniqueConstraint("date", name=op.f("uq_practice_sessions_date")),
        sa.CheckConstraint(
            f"status IN ({SESSION_STATUSES})", name=op.f("ck_practice_sessions_status_valid")
        ),
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
        sa.Column("timezone", sa.String(64), server_default="America/Montevideo", nullable=False),
        sa.Column(
            "theme_tokens",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "fonts", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("default_instrument", sa.String(20), server_default="electric", nullable=False),
        sa.Column(
            "tuning",
            postgresql.JSONB(),
            server_default=sa.text("""'["E2","A2","D3","G3","B3","E4"]'::jsonb"""),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_settings_single_row")),
        sa.CheckConstraint(
            f"default_instrument IN ({INSTRUMENTS})",
            name=op.f("ck_settings_default_instrument_valid"),
        ),
    )
    op.create_table(
        "reminder_rules",
        sa.Column("id", sa.Integer(), autoincrement=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_rules")),
        sa.Column(
            "excluded_weekdays",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("inactivity_threshold_days", sa.Integer(), server_default="3", nullable=False),
        sa.Column("preferred_window", postgresql.JSONB()),
        sa.CheckConstraint("id = 1", name=op.f("ck_reminder_rules_single_row")),
        sa.CheckConstraint(
            "excluded_weekdays <@ ARRAY[0,1,2,3,4,5,6]",
            name=op.f("ck_reminder_rules_weekdays_range"),
        ),
        sa.CheckConstraint(
            "inactivity_threshold_days > 0", name=op.f("ck_reminder_rules_threshold_positive")
        ),
    )


def downgrade() -> None:
    for table in (
        "reminder_rules",
        "settings",
        "practice_sessions",
        "exercise_completions",
        "exercises",
        "lessons",
        "levels",
    ):
        op.drop_table(table)
