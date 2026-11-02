"""Fixtures de base de datos: Postgres 16 efímero con testcontainers y migraciones aplicadas."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

API_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    return config


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Postgres de testcontainers, o la base vacía de `GUITAR_TEST_DATABASE_URL` si está."""
    external_url = os.environ.get("GUITAR_TEST_DATABASE_URL")
    if external_url:
        os.environ["DATABASE_URL"] = external_url
        yield external_url
        return
    with PostgresContainer("postgres:16", driver="psycopg") as postgres:
        url = postgres.get_connection_url()
        os.environ["DATABASE_URL"] = url  # lo lee alembic/env.py
        yield url


@pytest.fixture(scope="session")
def migrated_engine(database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config(), "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(migrated_engine: Engine) -> Iterator[Session]:
    """Sesión sobre el esquema migrado; vacía todas las tablas al terminar cada test."""
    with Session(migrated_engine) as db_session:
        yield db_session
        db_session.rollback()
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE exercise_completions, practice_sessions, exercises, lessons, levels, "
                "settings, reminder_rules, songs, song_sections, song_charts, audio_assets, "
                "analysis_jobs, corrections, chord_shape_preferences RESTART IDENTITY CASCADE"
            )
        )
