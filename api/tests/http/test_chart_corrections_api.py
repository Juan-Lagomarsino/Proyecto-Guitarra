import copy

import pytest
from fastapi.testclient import TestClient
from tests.http.test_songs_api import AUTH, chart_content

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.models import Correction, SongChart
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)
    return TestClient(app)


@pytest.fixture
def song_id(client):
    response = client.post("/api/v1/songs", json={"title": "T", "artist": "A"}, headers=AUTH)
    return response.json()["id"]


def chart_url(song_id, instrument="electric"):
    return f"/api/v1/songs/{song_id}/chart?instrument={instrument}"


def edited(content, **section_changes):
    body = copy.deepcopy(content.model_dump(mode="json"))
    body["sections"][0].update(section_changes)
    return body


def put_chart(client, song_id, body, instrument="electric"):
    return client.put(chart_url(song_id, instrument), json=body, headers=AUTH)


def test_put_requiere_token(client):
    assert client.put("/api/v1/songs/1/chart?instrument=electric", json={}).status_code == 401
    assert client.delete("/api/v1/songs/1/chart/user?instrument=electric").status_code == 401


def test_put_crea_version_de_usuario_y_get_la_devuelve(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    response = put_chart(client, song_id, edited(auto, name="Entrada"))
    assert response.status_code == 200
    body = response.json()
    assert (body["origin"], body["version"]) == ("user", 2)
    assert body["content"]["sections"][0]["name"] == "Entrada"
    current = client.get(chart_url(song_id), headers=AUTH).json()
    assert (current["origin"], current["version"]) == ("user", 2)


def test_la_version_de_usuario_gana_aunque_llegue_un_auto_nuevo(client, session, song_id):
    repo = SongRepository(session)
    auto = chart_content()
    repo.add_chart(song_id, "auto", auto)
    put_chart(client, song_id, edited(auto, name="Entrada"))
    repo.add_chart(song_id, "auto", chart_content(bpm=130))
    current = client.get(chart_url(song_id), headers=AUTH).json()
    assert current["origin"] == "user"
    assert current["content"]["sections"][0]["name"] == "Entrada"


def test_guarda_una_correccion_con_el_diff(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    new_chords = [
        {
            **auto.model_dump(mode="json")["sections"][0]["chords"][0],
            "name": "Dm",
            "shape": ["x", "x", 0, 2, 3, 1],
        }
    ]
    body = put_chart(client, song_id, edited(auto, name="Entrada", chords=new_chords)).json()
    correction = session.query(Correction).one()
    chart = session.get(SongChart, correction.song_chart_id)
    assert chart.version == body["version"]
    changes = correction.diff["sections"]["intro"]
    assert changes["name"] == {"from": "Intro", "to": "Entrada"}
    assert [c["name"] for c in changes["chords"]["from"]] == ["Am"]
    assert [c["name"] for c in changes["chords"]["to"]] == ["Dm"]


def test_el_diff_se_calcula_contra_la_version_vigente(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    first = put_chart(client, song_id, edited(auto, name="Entrada")).json()["content"]
    put_chart(client, song_id, edited(auto, name="Entrada", end_s=12))
    last = session.query(Correction).order_by(Correction.id.desc()).first()
    assert last.diff == {"sections": {"intro": {"end_s": {"from": 10.0, "to": 12.0}}}}
    assert first["sections"][0]["name"] == "Entrada"


def test_put_sin_cambios_no_crea_version(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    response = put_chart(client, song_id, auto.model_dump(mode="json"))
    assert response.status_code == 200
    assert (response.json()["origin"], response.json()["version"]) == ("auto", 1)
    assert session.query(Correction).count() == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body["sections"][0].update(start_s=20),  # inicio después del fin
        lambda body: body["sections"][0].update(name=""),
        lambda body: body["sections"][0].update(name="   "),
        lambda body: body["sections"][0]["chords"][0].update(t_s=50),  # acorde fuera
        lambda body: body["sections"][0].update(extra=1),  # campo desconocido
        lambda body: body.update(sections=[]),
    ],
)
def test_put_rechaza_charts_invalidos(client, session, song_id, mutate):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    body = copy.deepcopy(auto.model_dump(mode="json"))
    mutate(body)
    assert put_chart(client, song_id, body).status_code == 422
    assert session.query(SongChart).filter_by(song_id=song_id).count() == 1


def test_put_rechaza_instrumento_distinto_al_de_la_consulta(client, session, song_id):
    auto = chart_content("electric")
    SongRepository(session).add_chart(song_id, "auto", auto)
    response = put_chart(client, song_id, auto.model_dump(mode="json"), instrument="classical")
    assert response.status_code == 422


def test_put_sin_chart_previo_da_404(client, song_id):
    body = chart_content().model_dump(mode="json")
    assert put_chart(client, song_id, body).status_code == 404


def test_put_de_cancion_inexistente_da_404(client):
    body = chart_content().model_dump(mode="json")
    assert put_chart(client, 9999, body).status_code == 404


def test_volver_a_la_automatica(client, session, song_id):
    repo = SongRepository(session)
    auto = chart_content()
    repo.add_chart(song_id, "auto", auto)
    put_chart(client, song_id, edited(auto, name="Entrada"))
    repo.add_chart(song_id, "auto", chart_content(bpm=130))
    response = client.delete(
        f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["origin"], body["version"], body["content"]["bpm"]) == ("auto", 3, 130)
    assert client.get(chart_url(song_id), headers=AUTH).json()["origin"] == "auto"


def test_volver_a_la_automatica_conserva_el_historial(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put_chart(client, song_id, edited(auto, name="Entrada"))
    client.delete(f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH)
    assert session.query(Correction).count() == 1
    assert session.query(SongChart).filter_by(song_id=song_id, origin="user").count() == 1


def test_editar_despues_de_volver_crea_una_version_de_usuario_nueva(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    put_chart(client, song_id, edited(auto, name="Entrada"))
    client.delete(f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH)
    body = put_chart(client, song_id, edited(auto, name="Apertura")).json()
    assert (body["origin"], body["version"]) == ("user", 3)
    last = session.query(Correction).order_by(Correction.id.desc()).first()
    assert last.diff == {"sections": {"intro": {"name": {"from": "Intro", "to": "Apertura"}}}}


def test_volver_sin_version_de_usuario_da_404(client, session, song_id):
    SongRepository(session).add_chart(song_id, "auto", chart_content())
    response = client.delete(
        f"/api/v1/songs/{song_id}/chart/user?instrument=electric", headers=AUTH
    )
    assert response.status_code == 404


def test_volver_de_cancion_inexistente_da_404(client):
    response = client.delete("/api/v1/songs/9999/chart/user?instrument=electric", headers=AUTH)
    assert response.status_code == 404


def test_renombrar_no_cambia_el_id_de_la_seccion(client, session, song_id):
    """F2-T18 lee la sección del chart por `id == song_sections.slug`: el id es estable."""
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    body = put_chart(client, song_id, edited(auto, name="Entrada")).json()
    section = body["content"]["sections"][0]
    assert (section["id"], section["name"]) == ("intro", "Entrada")


def test_put_rechaza_cambiar_el_id_de_una_seccion_existente(client, session, song_id):
    auto = chart_content()
    SongRepository(session).add_chart(song_id, "auto", auto)
    response = put_chart(client, song_id, edited(auto, id="otro"))
    assert response.status_code == 422
    assert "intro" in response.json()["detail"]
