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


def test_token_del_worker_y_lease_con_defaults_y_variables(monkeypatch):
    monkeypatch.delenv("GUITAR_WORKER_TOKEN", raising=False)
    monkeypatch.delenv("GUITAR_JOB_LEASE_SECONDS", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.guitar_worker_token == ""
    assert defaults.guitar_job_lease_seconds == 300

    monkeypatch.setenv("GUITAR_WORKER_TOKEN", "w")
    monkeypatch.setenv("GUITAR_JOB_LEASE_SECONDS", "60")
    configured = Settings(_env_file=None)
    assert configured.guitar_worker_token == "w"
    assert configured.guitar_job_lease_seconds == 60
