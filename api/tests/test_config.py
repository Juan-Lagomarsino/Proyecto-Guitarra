from guitarra_api.config import Settings


def test_lee_variables_de_entorno(monkeypatch):
    monkeypatch.setenv("GUITAR_API_URL", "http://api.test:9000")
    monkeypatch.setenv("GUITAR_API_TOKEN", "secreto")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/x")

    settings = Settings(_env_file=None)

    assert settings.guitar_api_url == "http://api.test:9000"
    assert settings.guitar_api_token == "secreto"
    assert settings.database_url == "postgresql+psycopg://u:p@db/x"


def test_tiene_valores_por_defecto(monkeypatch):
    for nombre in ("GUITAR_API_URL", "GUITAR_API_TOKEN", "DATABASE_URL"):
        monkeypatch.delenv(nombre, raising=False)

    settings = Settings(_env_file=None)

    assert settings.guitar_api_url == "http://localhost:8000"
