from sqlalchemy import Engine

from guitarra_api.infra.db.session import create_db_engine


def test_create_db_engine_usa_la_url_dada():
    engine = create_db_engine("sqlite://")

    assert isinstance(engine, Engine)
    assert str(engine.url) == "sqlite://"
