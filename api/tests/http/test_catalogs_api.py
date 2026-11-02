import pytest
from fastapi.testclient import TestClient
from tests.http.test_songs_api import AUTH

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.main import create_app

TOKEN = "test-token"


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)
    return TestClient(app)


def test_requiere_token(client):
    assert client.get("/api/v1/strum-patterns").status_code == 401
    assert client.get("/api/v1/chords/shapes?name=Am").status_code == 401


def test_catalogo_de_rasgueos(client):
    response = client.get("/api/v1/strum-patterns", headers=AUTH)
    assert response.status_code == 200
    patterns = response.json()
    assert patterns
    assert {p["kind"] for p in patterns} == {"strum", "arpeggio"}
    folk = next(p for p in patterns if p["id"] == "rasgueo-4-folk")
    assert (folk["pattern"], folk["accent"], folk["beats_per_cycle"]) == ("D-DU-UDU", [0, 4], 4)


def test_formas_de_un_acorde_de_la_mas_facil_a_la_mas_dificil(client):
    response = client.get("/api/v1/chords/shapes?name=Am", headers=AUTH)
    assert response.status_code == 200
    shapes = response.json()
    assert shapes[0]["name"] == "Am"
    assert shapes[0]["shape"] == ["x", 0, 2, 2, 1, 0]
    assert shapes[0]["barre"] is None


def test_acorde_ilegible_da_422(client):
    assert client.get("/api/v1/chords/shapes?name=%3F%3F", headers=AUTH).status_code == 422


def test_formas_relativas_al_capo(client):
    # A con capo 2 se toca con las formas de G: la más fácil es G abierto
    shapes = client.get("/api/v1/chords/shapes?name=A&capo=2", headers=AUTH).json()
    assert shapes[0]["name"] == "G"
    assert shapes[0]["shape"] == [3, 2, 0, 0, 0, 3]
    assert client.get("/api/v1/chords/shapes?name=A", headers=AUTH).json()[0]["name"] == "A"


def test_capo_fuera_de_rango_da_422(client):
    assert client.get("/api/v1/chords/shapes?name=A&capo=13", headers=AUTH).status_code == 422
