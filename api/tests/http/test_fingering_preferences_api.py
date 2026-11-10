"""Preferencias de digitación aprendidas de las correcciones de riffs (F5-T07)."""

import pytest
from alembic import command
from fastapi.testclient import TestClient
from guitarra_core.fingering import FingeringPreferences
from guitarra_core.fingering_preferences import LEARNING_RATE, REJECTION_DECAY
from sqlalchemy import create_engine, inspect
from tests.http.test_songs_api import AUTH, chart_content

from conftest import alembic_config
from guitarra_api.config import Settings
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"
WORKER_TOKEN = "token-worker"
WORKER = {"Authorization": f"Bearer {WORKER_TOKEN}"}
URL = "/api/v1/preferences/fingering"
EMPTY = {"positions": {}, "zones": {}}
# La misma altura (A3 = 57): cuerda 3 traste 2 (G3 + 2) o cuerda 4 traste 7 (D3 + 7).
AUTO_NOTE = {"t": 0, "dur": 1, "string": 3, "fret": 2}
USER_NOTE = {"t": 0, "dur": 1, "string": 4, "fret": 7}
KEY_PITCH = "57"


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


def with_riff(events, capo=0):
    body = chart_content().model_dump(mode="json")
    body["capo"] = capo
    body["sections"][0]["riff"] = {"bpm": 100, "events": events}
    return body


def seed_auto_riff(session, song_id, events=(AUTO_NOTE,), capo=0):
    content = SongChartContent.model_validate(with_riff(list(events), capo))
    SongRepository(session).add_chart(song_id, "auto", content)


def put(client, song_id, body):
    return client.put(f"/api/v1/songs/{song_id}/chart?instrument=electric", json=body, headers=AUTH)


def prefs(client):
    return client.get(URL, headers=AUTH).json()


def test_lectura_requiere_token_y_arranca_vacia(client):
    assert client.get(URL).status_code == 401
    assert prefs(client) == EMPTY


def test_corregir_la_digitacion_del_riff_aprende(client, session, song_id):
    seed_auto_riff(session, song_id)
    assert put(client, song_id, with_riff([USER_NOTE])).status_code == 200
    learned = prefs(client)
    assert learned["positions"][KEY_PITCH]["4,7"] == pytest.approx(LEARNING_RATE)
    assert learned["zones"] == {"1": pytest.approx(LEARNING_RATE)}


def test_cambiar_solo_acordes_no_aprende(client, session, song_id):
    seed_auto_riff(session, song_id)
    body = with_riff([AUTO_NOTE])
    body["sections"][0]["chords"][0]["shape"] = [5, 7, 7, 5, 5, 5]
    assert put(client, song_id, body).status_code == 200
    assert prefs(client) == EMPTY


def test_cambiar_la_altura_no_es_digitacion(client, session, song_id):
    seed_auto_riff(session, song_id)
    put(client, song_id, with_riff([{**AUTO_NOTE, "fret": 5}]))
    assert prefs(client) == EMPTY


def test_riff_nuevo_sin_riff_vigente_no_aprende(client, session, song_id):
    SongRepository(session).add_chart(song_id, "auto", chart_content())
    put(client, song_id, with_riff([USER_NOTE]))
    assert prefs(client) == EMPTY


def test_se_compara_contra_la_vista_vigente_y_acumula(client, session, song_id):
    seed_auto_riff(session, song_id)
    put(client, song_id, with_riff([USER_NOTE]))
    put(client, song_id, with_riff([AUTO_NOTE]))  # vuelve a la original: rechaza 4,7
    positions = prefs(client)["positions"][KEY_PITCH]
    assert positions["3,2"] == pytest.approx(LEARNING_RATE)
    assert positions["4,7"] == pytest.approx(LEARNING_RATE * (1 - REJECTION_DECAY))


def test_descartar_la_version_de_usuario_no_borra_lo_aprendido(client, session, song_id):
    seed_auto_riff(session, song_id)
    put(client, song_id, with_riff([USER_NOTE]))
    before = prefs(client)
    response = client.delete(
        f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH
    )
    assert response.status_code == 200
    assert prefs(client) == before != EMPTY


def test_el_claim_trae_las_preferencias(client, session, song_id):
    seed_auto_riff(session, song_id)
    put(client, song_id, with_riff([USER_NOTE]))
    claimed = client.post("/api/v1/jobs/claim", json={"worker_id": "w1"}, headers=WORKER).json()
    assert claimed["fingering_preferences"] == prefs(client) != EMPTY


def test_el_claim_sin_aprendizaje_trae_la_estructura_vacia(client, song_id):
    claimed = client.post("/api/v1/jobs/claim", json={"worker_id": "w1"}, headers=WORKER).json()
    assert claimed["fingering_preferences"] == EMPTY


def test_migracion_0008_ida_y_vuelta(database_url):
    config = alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        assert "fingering_preferences" in inspect(engine).get_table_names()
        command.downgrade(config, "0007")
        assert "fingering_preferences" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
    finally:
        engine.dispose()


def claimed_preferences(client):
    claimed = client.post("/api/v1/jobs/claim", json={"worker_id": "w1"}, headers=WORKER).json()
    return FingeringPreferences.from_json(claimed["fingering_preferences"])


def test_con_capo_se_guarda_absoluto_y_vale_en_otro_capo(client, session, song_id):
    # capo 2: cuerda 3 traste 0 y cuerda 4 traste 5 suenan A3 (57); en el mastil: 3,2 y 4,7
    seed_auto_riff(session, song_id, events=[{**AUTO_NOTE, "fret": 0}], capo=2)
    put(client, song_id, with_riff([{**USER_NOTE, "fret": 5}], capo=2))
    stored = prefs(client)
    assert stored["positions"][KEY_PITCH]["4,7"] == pytest.approx(LEARNING_RATE)
    assert stored["zones"] == {"1": pytest.approx(LEARNING_RATE)}
    sin_capo = claimed_preferences(client).for_capo(0)
    assert sin_capo.position_weight(57, 4, 7) == pytest.approx(LEARNING_RATE)
    con_capo = FingeringPreferences.from_json(stored).for_capo(2)
    assert con_capo.position_weight(57, 4, 5) == pytest.approx(LEARNING_RATE)


def test_si_el_capo_cambia_en_la_misma_edicion_se_compara_en_absoluto(client, session, song_id):
    seed_auto_riff(session, song_id)  # capo 0: 3,2
    put(client, song_id, with_riff([{**USER_NOTE, "fret": 5}], capo=2))  # capo 2: 4,5 = 4,7
    assert prefs(client)["positions"][KEY_PITCH]["4,7"] == pytest.approx(LEARNING_RATE)
