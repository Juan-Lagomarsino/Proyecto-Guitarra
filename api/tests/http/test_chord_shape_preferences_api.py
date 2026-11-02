import copy

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from tests.http.test_songs_api import AUTH, chart_content

from conftest import alembic_config
from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"
WORKER_TOKEN = "token-worker"
WORKER = {"Authorization": f"Bearer {WORKER_TOKEN}"}
PREFS_URL = "/api/v1/preferences/chord-shapes"
EMA_ALPHA = 0.3
AM_BARRE_KEY = "5,7,7,5,5,5"


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        guitar_api_token=TOKEN, guitar_worker_token=WORKER_TOKEN
    )
    return TestClient(app)


@pytest.fixture
def song_id(client):
    response = client.post("/api/v1/songs", json={"title": "T", "artist": "A"}, headers=AUTH)
    return response.json()["id"]


def chart_url(song_id, instrument="electric"):
    return f"/api/v1/songs/{song_id}/chart?instrument={instrument}"


def edit_chord(content, **changes):
    body = copy.deepcopy(content.model_dump(mode="json"))
    body["sections"][0]["chords"][0].update(changes)
    return body


def put(client, song_id, body, instrument="electric"):
    return client.put(chart_url(song_id, instrument), json=body, headers=AUTH)


def prefs(client):
    return client.get(PREFS_URL, headers=AUTH).json()


def test_lectura_requiere_token_y_arranca_vacia(client):
    assert client.get(PREFS_URL).status_code == 401
    assert prefs(client) == {}


def test_put_con_otra_forma_guarda_la_preferencia(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put(client, song_id, edit_chord(auto, shape=[5, 7, 7, 5, 5, 5]))
    assert prefs(client) == {"electric": {"Am": {AM_BARRE_KEY: EMA_ALPHA}}}


def test_cambiar_el_nombre_no_guarda_preferencia_de_forma(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put(client, song_id, edit_chord(auto, name="C", shape=["x", 3, 2, 0, 1, 0]))
    assert prefs(client) == {}


def test_editar_otra_cosa_no_guarda_preferencia(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    body = copy.deepcopy(auto.model_dump(mode="json"))
    body["bpm"] = 120
    put(client, song_id, body)
    assert prefs(client) == {}


def test_la_misma_eleccion_repetida_en_otra_cancion_acumula(client, session, song_id):
    other = client.post("/api/v1/songs", json={"title": "U", "artist": "B"}, headers=AUTH).json()
    auto = chart_content()
    for sid in (song_id, other["id"]):
        SongRepository(session).add_chart(sid, "auto", auto)
        put(client, sid, edit_chord(auto, shape=[5, 7, 7, 5, 5, 5]))
    weight = prefs(client)["electric"]["Am"][AM_BARRE_KEY]
    assert weight == pytest.approx(EMA_ALPHA * (1 - EMA_ALPHA) + EMA_ALPHA)


def test_volver_a_la_automatica_no_borra_lo_aprendido(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put(client, song_id, edit_chord(auto, shape=[5, 7, 7, 5, 5, 5]))
    before = prefs(client)
    response = client.delete(
        f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH
    )
    assert response.status_code == 200
    assert prefs(client) == before != {}


def test_las_preferencias_son_por_instrumento(client, session, song_id):
    auto = chart_content("classical")
    SongRepository(session).add_chart(song_id, "auto", auto)
    put(client, song_id, edit_chord(auto, shape=[5, 7, 7, 5, 5, 5]), "classical")
    assert set(prefs(client)) == {"classical"}


def test_el_claim_trae_las_preferencias(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put(client, song_id, edit_chord(auto, shape=[5, 7, 7, 5, 5, 5]))
    claimed = client.post("/api/v1/jobs/claim", json={"worker_id": "w1"}, headers=WORKER).json()
    assert claimed["chord_shape_preferences"] == {"electric": {"Am": {AM_BARRE_KEY: EMA_ALPHA}}}


def test_el_claim_sin_aprendizaje_trae_un_dict_vacio(client, song_id):
    claimed = client.post("/api/v1/jobs/claim", json={"worker_id": "w1"}, headers=WORKER).json()
    assert claimed["chord_shape_preferences"] == {}


def test_migracion_0007_ida_y_vuelta(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        assert "chord_shape_preferences" in inspect(engine).get_table_names()
        command.downgrade(config, "0006")
        assert "chord_shape_preferences" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
    finally:
        engine.dispose()
