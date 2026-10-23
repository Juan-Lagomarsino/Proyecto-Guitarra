from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from guitarra_api.config import Settings as ApiConfig
from guitarra_api.domain.app_settings import DEFAULT_THEME_TOKENS, default_app_settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.http.routers import settings as settings_router
from guitarra_api.infra.db.models import Settings
from guitarra_api.infra.db.session import get_session

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(settings_router.router, prefix="/api/v1")
    app.dependency_overrides[get_api_settings] = lambda: ApiConfig(guitar_api_token="test-token")
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)


def _body(**overrides: object) -> dict[str, object]:
    return {**default_app_settings().model_dump(), **overrides}


def test_exige_token(client: TestClient) -> None:
    assert client.get("/api/v1/settings").status_code == 401
    assert client.put("/api/v1/settings", json=_body()).status_code == 401
    bad = {"Authorization": "Bearer otro"}
    assert client.get("/api/v1/settings", headers=bad).status_code == 401


def test_get_sin_fila_devuelve_defaults_sin_crearla(client: TestClient, session: Session) -> None:
    response = client.get("/api/v1/settings", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == default_app_settings().model_dump()
    assert response.json()["timezone"] == "America/Montevideo"
    assert session.scalar(select(func.count()).select_from(Settings)) == 0


def test_put_persiste_y_get_lo_devuelve(client: TestClient, session: Session) -> None:
    tokens = {**DEFAULT_THEME_TOKENS, "--accent": "rgb(10, 200, 30)", "--bg": "#000"}
    body = _body(
        timezone="Europe/Madrid",
        theme_tokens=tokens,
        default_instrument="classical",
        tuning=["D2", "A2", "D3", "G3", "B3", "E4"],
    )
    put = client.put("/api/v1/settings", json=body, headers=AUTH)
    assert put.status_code == 200
    assert put.json() == body

    session.expire_all()
    assert client.get("/api/v1/settings", headers=AUTH).json() == body
    row = session.get(Settings, 1)
    assert row is not None
    assert row.timezone == "Europe/Madrid"
    assert row.theme_tokens["--accent"] == "rgb(10, 200, 30)"


def test_put_dos_veces_hace_upsert_de_una_sola_fila(client: TestClient, session: Session) -> None:
    client.put("/api/v1/settings", json=_body(timezone="Europe/Madrid"), headers=AUTH)
    client.put("/api/v1/settings", json=_body(timezone="Asia/Tokyo"), headers=AUTH)
    assert session.scalar(select(func.count()).select_from(Settings)) == 1
    assert client.get("/api/v1/settings", headers=AUTH).json()["timezone"] == "Asia/Tokyo"


def test_put_rechaza_zona_horaria_invalida_y_no_persiste(
    client: TestClient, session: Session
) -> None:
    response = client.put("/api/v1/settings", json=_body(timezone="Mars/Base"), headers=AUTH)
    assert response.status_code == 422
    assert session.scalar(select(func.count()).select_from(Settings)) == 0


def test_put_rechaza_color_invalido(client: TestClient) -> None:
    tokens = {**DEFAULT_THEME_TOKENS, "--accent": "naranjaaa"}
    response = client.put("/api/v1/settings", json=_body(theme_tokens=tokens), headers=AUTH)
    assert response.status_code == 422


def test_put_rechaza_token_faltante(client: TestClient) -> None:
    tokens = {k: v for k, v in DEFAULT_THEME_TOKENS.items() if k != "--good"}
    response = client.put("/api/v1/settings", json=_body(theme_tokens=tokens), headers=AUTH)
    assert response.status_code == 422


def test_put_rechaza_instrumento_invalido(client: TestClient) -> None:
    response = client.put("/api/v1/settings", json=_body(default_instrument="banjo"), headers=AUTH)
    assert response.status_code == 422


def test_put_rechaza_fuente_peligrosa(client: TestClient) -> None:
    fonts = {"--font-display": "Anton", "--font-mono": "x; } body { color: red"}
    response = client.put("/api/v1/settings", json=_body(fonts=fonts), headers=AUTH)
    assert response.status_code == 422


def test_put_rechaza_afinacion_invalida(client: TestClient) -> None:
    response = client.put("/api/v1/settings", json=_body(tuning=["E2", "A2"]), headers=AUTH)
    assert response.status_code == 422


def test_get_completa_con_defaults_una_fila_incompleta(
    client: TestClient, session: Session
) -> None:
    tokens = {k: v for k, v in DEFAULT_THEME_TOKENS.items() if k != "--bg"}
    session.add(Settings(id=1, theme_tokens=tokens, fonts={}))
    session.commit()
    response = client.get("/api/v1/settings", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == default_app_settings().model_dump()
