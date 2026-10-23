from alembic import command
from sqlalchemy import create_engine, inspect

from conftest import alembic_config

EXPECTED_TABLES = {
    "levels",
    "lessons",
    "exercises",
    "exercise_completions",
    "practice_sessions",
    "settings",
    "reminder_rules",
}


def test_upgrade_crea_las_tablas_y_downgrade_las_borra(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
        command.downgrade(config, "base")
        assert not EXPECTED_TABLES & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
    finally:
        engine.dispose()


def _exercise_columns(engine) -> dict:
    return {column["name"]: column for column in inspect(engine).get_columns("exercises")}


def test_0002_agrega_description_nullable_y_el_downgrade_la_quita(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        column = _exercise_columns(engine)["description"]
        assert column["nullable"] is True
        command.downgrade(config, "0001")
        assert "description" not in _exercise_columns(engine)
        command.upgrade(config, "head")
    finally:
        engine.dispose()
