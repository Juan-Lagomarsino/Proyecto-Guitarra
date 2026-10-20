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
