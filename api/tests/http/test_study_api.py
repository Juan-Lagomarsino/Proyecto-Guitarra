import datetime as dt

import pytest
from fastapi.testclient import TestClient

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.models import Exercise, ExerciseCompletion, Lesson, Level
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOTATION = {"kind": "demo", "notes": [1, 2, 3]}


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)
    return TestClient(app)


@pytest.fixture
def datos(session):
    level = Level(slug="n1", position=1, name="Nivel 1", description="d", instrument="electric")
    level.lessons = [
        Lesson(slug="l2", position=2, title="Segunda", content_md="# dos"),
        Lesson(slug="l1", position=1, title="Primera", content_md="# uno"),
    ]
    session.add(level)
    session.flush()
    lesson = next(item for item in level.lessons if item.slug == "l1")
    for slug in ("e1", "e2"):
        session.add(
            Exercise(
                lesson_id=lesson.id,
                slug=slug,
                title=slug.upper(),
                type="riff",
                instrument="electric",
                notation=NOTATION,
                bpm_start=60,
                bpm_target=100,
                duration_min=5,
                category="riff",
            )
        )
    session.commit()
    ids = {item.slug: item.id for item in session.query(Exercise)}
    return {"level_id": level.id, "lesson_id": lesson.id, "exercises": ids}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/levels"),
        ("get", "/api/v1/levels/1/lessons"),
        ("get", "/api/v1/lessons/1"),
        ("get", "/api/v1/exercises/1"),
        ("post", "/api/v1/exercises/1/complete"),
    ],
)
def test_sin_token_o_token_malo_devuelve_401(client, method, path):
    assert getattr(client, method)(path).status_code == 401
    bad = {"Authorization": "Bearer otro"}
    assert getattr(client, method)(path, headers=bad).status_code == 401


@pytest.mark.parametrize(
    "path",
    ["/api/v1/levels/999/lessons", "/api/v1/lessons/999", "/api/v1/exercises/999"],
)
def test_ids_inexistentes_devuelven_404(client, path):
    assert client.get(path, headers=AUTH).status_code == 404


def test_complete_ejercicio_inexistente_devuelve_404(client):
    body = {"bpm_logrado": 80, "instrumento": "electric"}
    assert client.post("/api/v1/exercises/999/complete", json=body, headers=AUTH).status_code == 404


def test_lista_niveles(client, datos):
    response = client.get("/api/v1/levels", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": datos["level_id"],
            "slug": "n1",
            "position": 1,
            "name": "Nivel 1",
            "description": "d",
            "instrument": "electric",
        }
    ]


def test_lecciones_del_nivel_ordenadas_por_posicion(client, datos):
    response = client.get(f"/api/v1/levels/{datos['level_id']}/lessons", headers=AUTH)

    assert response.status_code == 200
    assert [item["slug"] for item in response.json()] == ["l1", "l2"]


def test_leccion_incluye_contenido_y_ejercicios(client, datos):
    response = client.get(f"/api/v1/lessons/{datos['lesson_id']}", headers=AUTH)

    body = response.json()
    assert body["content_md"] == "# uno"
    assert [item["slug"] for item in body["exercises"]] == ["e1", "e2"]


def test_ejercicio_sin_completar_tiene_mejor_bpm_null_y_notacion(client, datos):
    response = client.get(f"/api/v1/exercises/{datos['exercises']['e1']}", headers=AUTH)

    body = response.json()
    assert body["best_bpm"] is None
    assert body["notation"] == NOTATION
    assert body["bpm_target"] == 100


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"bpm_logrado": 80},
        {"instrumento": "electric"},
        {"bpm_logrado": 0, "instrumento": "electric"},
        {"bpm_logrado": -5, "instrumento": "electric"},
        {"bpm_logrado": "rapido", "instrumento": "electric"},
        {"bpm_logrado": 80, "instrumento": "banjo"},
    ],
)
def test_complete_con_body_invalido_devuelve_422(client, datos, body):
    path = f"/api/v1/exercises/{datos['exercises']['e1']}/complete"

    assert client.post(path, json=body, headers=AUTH).status_code == 422


def test_complete_persiste_con_timestamp_utc(client, datos, session):
    exercise_id = datos["exercises"]["e1"]
    before = dt.datetime.now(dt.UTC)

    response = client.post(
        f"/api/v1/exercises/{exercise_id}/complete",
        json={"bpm_logrado": 85, "instrumento": "classical"},
        headers=AUTH,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["exercise_id"] == exercise_id
    assert body["bpm_logrado"] == 85
    assert body["instrumento"] == "classical"
    assert body["best_bpm"] == 85
    completed_at = dt.datetime.fromisoformat(body["completed_at"])
    assert completed_at.utcoffset() == dt.timedelta(0)
    assert before <= completed_at <= dt.datetime.now(dt.UTC)
    session.expire_all()
    stored = session.query(ExerciseCompletion).one()
    assert stored.bpm_achieved == 85
    assert stored.instrument == "classical"


def test_mejor_bpm_es_el_maximo_aunque_el_ultimo_sea_menor(client, datos):
    exercise_id = datos["exercises"]["e1"]
    path = f"/api/v1/exercises/{exercise_id}/complete"
    for bpm in (70, 95, 80):
        client.post(path, json={"bpm_logrado": bpm, "instrumento": "electric"}, headers=AUTH)

    response = client.get(f"/api/v1/exercises/{exercise_id}", headers=AUTH)

    assert response.json()["best_bpm"] == 95
    other = client.get(f"/api/v1/exercises/{datos['exercises']['e2']}", headers=AUTH)
    assert other.json()["best_bpm"] is None


def test_docs_expone_los_esquemas(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/exercises/{exercise_id}/complete" in paths
    assert "/api/v1/levels" in paths
