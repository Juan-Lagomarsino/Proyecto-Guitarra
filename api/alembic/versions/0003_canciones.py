"""Canciones, charts, cola de análisis y ejercicios de canción.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

INSTRUMENTS = "'classical', 'electric'"
SONG_SOURCES = "'youtube', 'spotify', 'search'"
ANALYSIS_STATUSES = "'queued', 'processing', 'ready', 'error'"
CHART_ORIGINS = "'auto', 'cifraclub', 'user'"
AUDIO_ASSET_KINDS = "'original', 'no_guitar', 'stem'"
JOB_STATUSES = "'queued', 'running', 'done', 'error'"
XOR_CHECK = "(lesson_id IS NULL) <> (song_section_id IS NULL)"


def _id_column() -> sa.Column:
    return sa.Column("id", sa.Integer())


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _song_fk(table: str) -> sa.Column:
    return sa.Column(
        "song_id",
        sa.Integer(),
        sa.ForeignKey("songs.id", ondelete="CASCADE", name=op.f(f"fk_{table}_song_id_songs")),
        nullable=False,
    )


def upgrade() -> None:
    _create_songs()
    _create_song_sections()
    _create_song_charts()
    _create_audio_assets()
    _create_analysis_jobs()
    _create_corrections()
    _link_exercises_to_song_sections()


def downgrade() -> None:
    # Los ejercicios de canción no existen en 0002: se borran para volver a lesson_id NOT NULL.
    op.execute("DELETE FROM exercises WHERE lesson_id IS NULL")
    op.drop_constraint(op.f("ck_exercises_lesson_xor_song_section"), "exercises", type_="check")
    op.drop_index(op.f("ix_exercises_song_section_id"), table_name="exercises")
    op.drop_constraint(
        op.f("fk_exercises_song_section_id_song_sections"), "exercises", type_="foreignkey"
    )
    op.drop_column("exercises", "song_section_id")
    op.alter_column("exercises", "lesson_id", existing_type=sa.Integer(), nullable=False)
    for table in (
        "corrections",
        "analysis_jobs",
        "audio_assets",
        "song_charts",
        "song_sections",
        "songs",
    ):
        op.drop_table(table)


def _create_songs() -> None:
    op.create_table(
        "songs",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_songs")),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("artist", sa.String(300), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("youtube_id", sa.String(32)),
        sa.Column("spotify_id", sa.String(64)),
        sa.Column("duration_s", sa.Float()),
        sa.Column("bpm", sa.Float()),
        sa.Column("key", sa.String(20)),
        sa.Column("year", sa.Integer()),
        sa.Column("analysis_status", sa.String(20), server_default="queued", nullable=False),
        _created_at(),
        sa.UniqueConstraint("youtube_id", name=op.f("uq_songs_youtube_id")),
        sa.UniqueConstraint("spotify_id", name=op.f("uq_songs_spotify_id")),
        sa.CheckConstraint(f"source IN ({SONG_SOURCES})", name=op.f("ck_songs_source_valid")),
        sa.CheckConstraint(
            f"analysis_status IN ({ANALYSIS_STATUSES})", name=op.f("ck_songs_status_valid")
        ),
        sa.CheckConstraint(
            "duration_s IS NULL OR duration_s > 0", name=op.f("ck_songs_duration_positive")
        ),
        sa.CheckConstraint("bpm IS NULL OR bpm > 0", name=op.f("ck_songs_bpm_positive")),
    )


def _create_song_sections() -> None:
    op.create_table(
        "song_sections",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_song_sections")),
        _song_fk("song_sections"),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("start_s", sa.Float(), nullable=False),
        sa.Column("end_s", sa.Float(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("song_id", "position", name=op.f("uq_song_sections_song_position")),
        sa.UniqueConstraint("song_id", "slug", name=op.f("uq_song_sections_song_slug")),
        sa.CheckConstraint(
            "start_s >= 0 AND start_s < end_s", name=op.f("ck_song_sections_times_valid")
        ),
    )
    op.create_index(op.f("ix_song_sections_song_id"), "song_sections", ["song_id"])


def _create_song_charts() -> None:
    op.create_table(
        "song_charts",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_song_charts")),
        _song_fk("song_charts"),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float()),
        _created_at(),
        sa.UniqueConstraint(
            "song_id", "instrument", "version", name=op.f("uq_song_charts_version")
        ),
        sa.CheckConstraint(
            f"instrument IN ({INSTRUMENTS})", name=op.f("ck_song_charts_instrument_valid")
        ),
        sa.CheckConstraint(
            f"origin IN ({CHART_ORIGINS})", name=op.f("ck_song_charts_origin_valid")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_song_charts_version_positive")),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name=op.f("ck_song_charts_confidence_range"),
        ),
    )
    op.create_index(op.f("ix_song_charts_song_id"), "song_charts", ["song_id"])


def _create_audio_assets() -> None:
    op.create_table(
        "audio_assets",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audio_assets")),
        _song_fk("audio_assets"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("format", sa.String(10), nullable=False),
        sa.CheckConstraint(
            f"kind IN ({AUDIO_ASSET_KINDS})", name=op.f("ck_audio_assets_kind_valid")
        ),
    )
    op.create_index(op.f("ix_audio_assets_song_id"), "audio_assets", ["song_id"])


def _create_analysis_jobs() -> None:
    op.create_table(
        "analysis_jobs",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_jobs")),
        _song_fk("analysis_jobs"),
        sa.Column("type", sa.String(30), server_default="analyze", nullable=False),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("error", sa.Text()),
        _created_at(),
        sa.Column("claimed_by", sa.String(120)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("current_step", sa.String(60)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            f"status IN ({JOB_STATUSES})", name=op.f("ck_analysis_jobs_status_valid")
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_analysis_jobs_attempts_non_negative")),
        sa.CheckConstraint(
            "max_attempts >= 1", name=op.f("ck_analysis_jobs_max_attempts_positive")
        ),
    )
    op.create_index(op.f("ix_analysis_jobs_song_id"), "analysis_jobs", ["song_id"])
    op.create_index(
        "ix_analysis_jobs_status_lease_until", "analysis_jobs", ["status", "lease_until"]
    )


def _create_corrections() -> None:
    op.create_table(
        "corrections",
        _id_column(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corrections")),
        sa.Column(
            "song_chart_id",
            sa.Integer(),
            sa.ForeignKey(
                "song_charts.id",
                ondelete="CASCADE",
                name=op.f("fk_corrections_song_chart_id_song_charts"),
            ),
            nullable=False,
        ),
        sa.Column("diff", postgresql.JSONB(), nullable=False),
        _created_at(),
    )
    op.create_index(op.f("ix_corrections_song_chart_id"), "corrections", ["song_chart_id"])


def _link_exercises_to_song_sections() -> None:
    """`lesson_id` pasa a nullable; las filas existentes ya lo tienen, así que cumplen el XOR."""
    op.alter_column("exercises", "lesson_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "exercises",
        sa.Column(
            "song_section_id",
            sa.Integer(),
            sa.ForeignKey(
                "song_sections.id",
                ondelete="CASCADE",
                name=op.f("fk_exercises_song_section_id_song_sections"),
            ),
        ),
    )
    op.create_index(op.f("ix_exercises_song_section_id"), "exercises", ["song_section_id"])
    op.create_check_constraint(op.f("ck_exercises_lesson_xor_song_section"), "exercises", XOR_CHECK)
