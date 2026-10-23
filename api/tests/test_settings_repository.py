from sqlalchemy.orm import Session

from guitarra_api.domain.app_settings import DEFAULT_THEME_TOKENS, default_app_settings
from guitarra_api.infra.db.models import Settings
from guitarra_api.infra.db.repositories.settings import SettingsRepository


def test_fila_con_json_vacio_devuelve_defaults(session: Session) -> None:
    session.add(Settings(id=1, theme_tokens={}, fonts={}))
    session.commit()
    session.expire_all()
    assert SettingsRepository(session).get() == default_app_settings()


def test_fila_con_server_default_vacio_devuelve_defaults(session: Session) -> None:
    session.execute(Settings.__table__.insert().values(id=1))  # server_default '{}'
    session.commit()
    assert SettingsRepository(session).get() == default_app_settings()


def test_fila_con_un_token_de_menos_lo_completa(session: Session) -> None:
    tokens = {k: v for k, v in DEFAULT_THEME_TOKENS.items() if k != "--good"}
    tokens["--accent"] = "#123456"
    session.add(Settings(id=1, theme_tokens=tokens))
    session.commit()
    result = SettingsRepository(session).get()
    assert result.theme_tokens["--good"] == DEFAULT_THEME_TOKENS["--good"]
    assert result.theme_tokens["--accent"] == "#123456"


def test_descarta_desconocidos_y_reemplaza_invalidos(session: Session) -> None:
    tokens = {**DEFAULT_THEME_TOKENS, "--viejo": "#fff", "--bg": "no-es-color"}
    session.add(Settings(id=1, theme_tokens=tokens, timezone="Mars/Base", tuning=["E2"]))
    session.commit()
    result = SettingsRepository(session).get()
    assert "--viejo" not in result.theme_tokens
    assert result.theme_tokens["--bg"] == DEFAULT_THEME_TOKENS["--bg"]
    assert result.timezone == "America/Montevideo"
    assert result.tuning == default_app_settings().tuning
