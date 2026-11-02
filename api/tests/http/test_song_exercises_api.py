import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from guitarra_api.config import Settings
from guitarra_api.domain.notation import Notation
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.http.auth import get_api_settings
from guitarra_api.http.clock import get_clock
from guitarra_api.infra.db.models import Exercise, Lesson, Level, SongSection
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"

AUTH = {"Authorization": f"Bearer {TOKEN}"}

NOW = dt.datetime(2026, 3, 10, 15, 0, tzinfo=dt.UTC)

AM = ["x", 0, 2, 2, 1, 0]

F = [1, 3, 3, 2, 1, 1]


@pytest.fixture
def client(session):

    app = create_app()

    app.dependency_overrides[get_session] = lambda: session

    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)

    app.dependency_overrides[get_clock] = lambda: lambda: NOW

    return TestClient(app)


def chart(bpm=100, origin_sections=None) -> SongChartContent:

    sections = origin_sections or [
        {
            "id": "intro",
            "name": "Intro",
            "start_s": 0,
            "end_s": 16,
            "order": 0,
            "chord_source": "detected",
            "chords": [
                {"t_s": 0, "name": "Am", "shape": AM, "confidence": 0.9},
                {"t_s": 4, "name": "F", "shape": F, "confidence": 0.9},
            ],
            "strum": {"pattern": "D-DU-UDU", "pattern_id": "p1", "confidence": 0.8},
        },
        {
            "id": "vacia",
            "name": "Vacía",
            "start_s": 16,
            "end_s": 20,
            "order": 1,
            "chord_source": "detected",
        },
    ]

    return SongChartContent.model_validate(
        {"instrument": "electric", "bpm": bpm, "sections": sections}
    )


@pytest.fixture
def song(session):
    """Canción con chart eléctrico y dos secciones, más una sección stale."""

    repo = SongRepository(session)

    created = repo.add_song(title="Come Together", artist="Beatles", source="search")

    created.sections = [
        SongSection(slug="intro", name="Intro", start_s=0, end_s=16, position=0),
        SongSection(slug="vacia", name="Vacía", start_s=16, end_s=20, position=1),
        SongSection(slug="viejo", name="Viejo", start_s=20, end_s=30, position=-1, stale=True),
    ]

    repo.add_chart(created.id, "auto", chart())

    session.commit()

    return created


def section_id(song, slug):

    return next(s.id for s in song.sections if s.slug == slug)


def url(song, slug="intro"):

    return f"/api/v1/songs/{song.id}/sections/{section_id(song, slug)}/exercises"


def create(client, song, type="chords", slug="intro", instrument="electric"):

    return client.post(url(song, slug), json={"type": type, "instrument": instrument}, headers=AUTH)


def test_requiere_token(client, song):

    assert (
        client.post(url(song), json={"type": "chords", "instrument": "electric"}).status_code == 401
    )

    assert client.get(f"/api/v1/songs/{song.id}/exercises").status_code == 401


@pytest.mark.parametrize("kind", ["chords", "strumming"])
def test_crea_un_ejercicio_valido_para_cada_tipo(client, song, kind):

    response = create(client, song, kind)

    assert response.status_code == 201

    body = response.json()

    assert body["type"] == kind

    assert body["lesson_id"] is None and body["song_section_id"] == section_id(song, "intro")

    assert "Come Together" in body["title"] and "Intro" in body["title"]

    assert (body["bpm_start"], body["bpm_target"]) == (70, 100)

    assert body["instrument"] == "electric" and body["duration_min"] > 0

    notation = Notation.model_validate(body["notation"])

    assert [c.name for c in notation.chords] == ["Am", "F"]

    assert bool(notation.strum) == (kind == "strumming")


def test_usa_la_version_de_usuario_del_chart_si_existe(client, session, song):

    edited = chart().model_copy(deep=True)

    edited.sections[0].chords[1].name = "Dm"

    SongRepository(session).add_chart(song.id, "user", edited)

    notation = create(client, song).json()["notation"]

    assert [c["name"] for c in notation["chords"]] == ["Am", "Dm"]


def test_cada_pedido_crea_un_ejercicio_nuevo_con_slug_unico(client, song):

    first, second = create(client, song).json(), create(client, song).json()

    assert first["id"] != second["id"] and first["slug"] != second["slug"]

    listed = client.get(f"/api/v1/songs/{song.id}/exercises", headers=AUTH).json()

    assert [e["id"] for e in listed] == [first["id"], second["id"]]


def test_404_si_la_cancion_no_existe(client, song):

    response = client.post(
        "/api/v1/songs/999/sections/1/exercises",
        json={"type": "chords", "instrument": "electric"},
        headers=AUTH,
    )

    assert response.status_code == 404

    assert client.get("/api/v1/songs/999/exercises", headers=AUTH).status_code == 404


def test_404_si_la_seccion_no_existe(client, song):

    response = client.post(
        f"/api/v1/songs/{song.id}/sections/9999/exercises",
        json={"type": "chords", "instrument": "electric"},
        headers=AUTH,
    )

    assert response.status_code == 404


def test_404_si_la_seccion_es_de_otra_cancion(client, session, song):

    other = SongRepository(session).add_song(title="Otra", artist="X", source="search")

    other.sections = [SongSection(slug="intro", name="Intro", start_s=0, end_s=10, position=0)]

    session.commit()

    response = client.post(
        f"/api/v1/songs/{song.id}/sections/{other.sections[0].id}/exercises",
        json={"type": "chords", "instrument": "electric"},
        headers=AUTH,
    )

    assert response.status_code == 404


def test_404_si_no_hay_chart_del_instrumento(client, song):

    assert create(client, song, instrument="classical").status_code == 404


def test_422_si_la_seccion_no_tiene_acordes(client, song):

    response = create(client, song, slug="vacia")

    assert response.status_code == 422

    assert "acordes" in response.json()["detail"]


def test_422_si_el_tipo_es_desconocido(client, song):

    assert create(client, song, type="escala").status_code == 422


def test_seccion_stale_ya_no_sale_del_chart_pero_sus_ejercicios_siguen(client, session, song):

    exercise_id = create(client, song).json()["id"]

    session.get(SongSection, section_id(song, "intro")).stale = True

    session.commit()

    assert create(client, song, slug="viejo").status_code == 409

    assert client.get(f"/api/v1/exercises/{exercise_id}", headers=AUTH).status_code == 200

    complete = client.post(
        f"/api/v1/exercises/{exercise_id}/complete",
        json={"bpm_logrado": 80, "instrumento": "electric"},
        headers=AUTH,
    )

    assert complete.status_code == 201


def test_terminé_suma_a_la_racha_y_al_calendario(client, song):

    exercise_id = create(client, song).json()["id"]

    detail = client.get(f"/api/v1/exercises/{exercise_id}", headers=AUTH).json()

    assert detail["best_bpm"] is None

    done = client.post(
        f"/api/v1/exercises/{exercise_id}/complete",
        json={"bpm_logrado": 75, "instrumento": "electric"},
        headers=AUTH,
    )

    assert done.status_code == 201 and done.json()["best_bpm"] == 75

    summary = client.get("/api/v1/progress/summary", headers=AUTH).json()

    assert summary["practiced_days"] == 1

    calendar = client.get("/api/v1/progress/calendar?from=2000-01-01&to=2100-01-01", headers=AUTH)

    assert [day["count"] for day in calendar.json()["days"]] == [1]


def test_resumen_cuenta_canciones_en_curso(client, session, song):

    url_summary = "/api/v1/progress/summary"

    assert client.get(url_summary, headers=AUTH).json()["songs_in_progress"] == 0

    create(client, song)

    create(client, song, "strumming")

    assert client.get(url_summary, headers=AUTH).json()["songs_in_progress"] == 1

    other = SongRepository(session).add_song(title="Otra", artist="X", source="search")

    other.sections = [SongSection(slug="a", name="A", start_s=0, end_s=5, position=0)]

    session.commit()

    assert client.get(url_summary, headers=AUTH).json()["songs_in_progress"] == 1


def test_el_planificador_ignora_los_ejercicios_de_cancion(client, session, song):

    level = Level(slug="n1", position=1, name="N1", instrument="electric")

    level.lessons = [Lesson(slug="l1", position=1, title="L", content_md="")]

    session.add(level)

    session.flush()

    for category in ("warmup", "technique", "riff", "improvisation"):
        session.add(
            Exercise(
                lesson_id=level.lessons[0].id,
                slug=f"e-{category}",
                title=category,
                type="riff",
                instrument="electric",
                notation={},
                bpm_start=60,
                bpm_target=80,
                duration_min=5,
                category=category,
            )
        )

    session.commit()

    song_exercise_id = create(client, song).json()["id"]

    body = client.get("/api/v1/sessions/today", headers=AUTH).json()

    planned = [e["id"] for block in body["blocks"] for e in block["exercises"]]

    assert planned and song_exercise_id not in planned

    levels = client.get("/api/v1/progress/summary", headers=AUTH).json()["levels"]

    assert [level["total"] for level in levels] == [4]


def test_la_base_exige_leccion_o_seccion_pero_no_ambas(session, song):

    level = Level(slug="n1", position=1, name="N1", instrument="electric")

    level.lessons = [Lesson(slug="l1", position=1, title="L", content_md="")]

    session.add(level)

    session.commit()

    lesson_id, section = level.lessons[0].id, song.sections[0].id

    common = {
        "title": "x",
        "type": "riff",
        "instrument": "electric",
        "notation": {},
        "duration_min": 5,
        "category": "riff",
    }

    for index, links in enumerate([{}, {"lesson_id": lesson_id, "song_section_id": section}]):
        session.add(Exercise(slug=f"x{index}", **common, **links))

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_nombre_y_acordes_salen_del_chart_y_no_de_song_sections(client, session, song):

    edited = chart().model_copy(deep=True)

    edited.sections[0].name = "Introducción"

    edited.sections[0].end_s = 12

    SongRepository(session).add_chart(song.id, "user", edited)

    section = session.get(SongSection, section_id(song, "intro"))

    section.name, section.end_s = "Nombre viejo", 99

    session.commit()

    body = create(client, song).json()

    assert "Introducción" in body["title"] and "Nombre viejo" not in body["title"]

    assert body["song_section_id"] == section.id
