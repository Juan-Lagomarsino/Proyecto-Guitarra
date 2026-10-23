import datetime as dt

import pytest
from fastapi.testclient import TestClient

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.http.clock import get_clock
from guitarra_api.infra.db.models import Exercise, ExerciseCompletion, Lesson, Level
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
NOTATION = {"kind": "demo", "notes": [1, 2, 3]}
# Martes 10 de marzo de 2026, 12:00 en Montevideo (UTC-3).
NOW = dt.datetime(2026, 3, 10, 15, 0, tzinfo=dt.UTC)
CATEGORIES = ("warmup", "technique", "riff", "improvisation")


class FakeClock:
    def __init__(self, now: dt.datetime) -> None:
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture
def clock():
    return FakeClock(NOW)


@pytest.fixture
def client(session, clock):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)
    app.dependency_overrides[get_clock] = lambda: clock
    return TestClient(app)


@pytest.fixture
def curriculum(session):
    """Dos niveles; 4 ejercicios de 5 min por categoría en el nivel 1 y 2 en el nivel 2."""
    exercises: dict[str, int] = {}
    for position in (1, 2):
        level = Level(
            slug=f"n{position}", position=position, name=f"Nivel {position}", instrument="electric"
        )
        lesson = Lesson(slug=f"l{position}", position=1, title="Lección", content_md="")
        level.lessons = [lesson]
        session.add(level)
        session.flush()
        per_category = 4 if position == 1 else 2
        for category in CATEGORIES:
            for index in range(per_category):
                slug = f"n{position}-{category}-{index}"
                exercise = Exercise(
                    lesson_id=lesson.id,
                    slug=slug,
                    title=slug,
                    type="riff",
                    instrument="electric",
                    notation=NOTATION,
                    bpm_start=60,
                    bpm_target=100,
                    duration_min=5,
                    category=category,
                    description=f"Descripción de {slug}",
                )
                session.add(exercise)
                session.flush()
                exercises[slug] = exercise.id
    session.commit()
    return exercises


def complete(session, exercise_id: int, when: dt.datetime, bpm: int = 80) -> None:
    session.add(
        ExerciseCompletion(
            exercise_id=exercise_id, completed_at=when, bpm_achieved=bpm, instrument="electric"
        )
    )
    session.commit()


def days_ago(count: int, hour: int = 15) -> dt.datetime:
    return (NOW - dt.timedelta(days=count)).replace(hour=hour)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/progress/summary"),
        ("get", "/api/v1/progress/calendar?from=2026-03-01&to=2026-03-10"),
        ("get", "/api/v1/sessions/today"),
        ("post", "/api/v1/sessions/today/regenerate"),
        ("get", "/api/v1/reminders/rules"),
        ("put", "/api/v1/reminders/rules"),
    ],
)
def test_sin_token_o_token_malo_devuelve_401(client, method, path):
    assert getattr(client, method)(path).status_code == 401
    bad = {"Authorization": "Bearer otro"}
    assert getattr(client, method)(path, headers=bad).status_code == 401


# --- progreso ---------------------------------------------------------------


def test_resumen_sin_datos_es_cero(client, curriculum):
    body = client.get("/api/v1/progress/summary", headers=AUTH).json()

    assert body["current_streak"] == 0
    assert body["max_streak"] == 0
    assert body["practiced_days"] == 0
    assert [(n["position"], n["completed"], n["total"]) for n in body["levels"]] == [
        (1, 0, 16),
        (2, 0, 8),
    ]
    assert set(body["levels"][0]) == {"level_id", "slug", "position", "name", "completed", "total"}


def test_completar_ejercicios_cambia_racha_calendario_y_avance(client, session, curriculum):
    first, second = curriculum["n1-warmup-0"], curriculum["n1-riff-0"]
    complete(session, first, days_ago(2))
    complete(session, first, days_ago(1))
    complete(session, second, days_ago(1, hour=16))
    complete(session, second, days_ago(0, hour=14))

    summary = client.get("/api/v1/progress/summary", headers=AUTH).json()
    calendar = client.get(
        "/api/v1/progress/calendar?from=2026-03-01&to=2026-03-31", headers=AUTH
    ).json()

    assert summary["current_streak"] == 3
    assert summary["max_streak"] == 3
    assert summary["practiced_days"] == 3
    assert summary["levels"][0]["completed"] == 2  # ejercicios distintos, no completions
    assert calendar == {
        "days": [
            {"date": "2026-03-08", "count": 1},
            {"date": "2026-03-09", "count": 2},
            {"date": "2026-03-10", "count": 1},
        ]
    }


def test_calendario_recorta_al_rango(client, session, curriculum):
    complete(session, curriculum["n1-warmup-0"], days_ago(5))
    complete(session, curriculum["n1-warmup-0"], days_ago(0))

    response = client.get("/api/v1/progress/calendar?from=2026-03-10&to=2026-03-10", headers=AUTH)

    assert response.json() == {"days": [{"date": "2026-03-10", "count": 1}]}


def test_dia_excluido_en_las_reglas_afecta_la_racha(client, session, curriculum):
    # Sábado 7 y martes 10; domingo y lunes sin práctica.
    complete(session, curriculum["n1-warmup-0"], days_ago(3))
    complete(session, curriculum["n1-warmup-0"], days_ago(0))
    url = "/api/v1/progress/summary"

    assert client.get(url, headers=AUTH).json()["current_streak"] == 1

    rules = {"excluded_weekdays": [6, 0], "inactivity_threshold_days": 3}
    assert client.put("/api/v1/reminders/rules", json=rules, headers=AUTH).status_code == 200

    summary = client.get(url, headers=AUTH).json()
    assert summary["current_streak"] == 2
    assert summary["max_streak"] == 2


def test_cambiar_la_zona_cambia_el_dia_de_una_completion_cerca_de_medianoche(
    client, session, curriculum
):
    # 02:00 UTC del 10: son las 23:00 del 9 en Montevideo y las 11:00 del 10 en Tokio.
    complete(session, curriculum["n1-warmup-0"], dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC))
    url = "/api/v1/progress/calendar?from=2026-03-01&to=2026-03-31"

    assert client.get(url, headers=AUTH).json()["days"] == [{"date": "2026-03-09", "count": 1}]

    settings = client.get("/api/v1/settings", headers=AUTH).json()
    settings["timezone"] = "Asia/Tokyo"
    assert client.put("/api/v1/settings", json=settings, headers=AUTH).status_code == 200

    assert client.get(url, headers=AUTH).json()["days"] == [{"date": "2026-03-10", "count": 1}]


@pytest.mark.parametrize(
    "query",
    [
        "from=2026-03-10&to=2026-03-01",
        "from=2026-03-01",
        "to=2026-03-01",
        "from=ayer&to=hoy",
        "",
    ],
)
def test_calendario_con_parametros_invalidos_devuelve_422(client, query):
    response = client.get(f"/api/v1/progress/calendar?{query}", headers=AUTH)

    assert response.status_code == 422


# --- sesión del día ---------------------------------------------------------


def exercise_ids(body: dict) -> list[int]:
    return [item["id"] for block in body["blocks"] for item in block["exercises"]]


def test_sesion_de_hoy_es_estable_y_tiene_el_contrato_esperado(client, curriculum):
    first = client.get("/api/v1/sessions/today", headers=AUTH).json()
    second = client.get("/api/v1/sessions/today", headers=AUTH).json()

    assert first == second
    assert first["date"] == "2026-03-10"
    assert first["status"] == "planned"
    assert 15 <= first["total_minutes"] <= 25
    assert [block["category"] for block in first["blocks"]][0] == "warmup"
    exercise = first["blocks"][0]["exercises"][0]
    assert set(exercise) == {
        "id",
        "title",
        "category",
        "minutes",
        "duration_min",
        "bpm_target",
        "description",
        "completed_today",
    }
    assert exercise["completed_today"] is False
    assert exercise["bpm_target"] == 100
    assert exercise["description"] == f"Descripción de {exercise['title']}"


def test_regenerate_reemplaza_la_sesion_de_hoy(client, curriculum):
    before = client.get("/api/v1/sessions/today", headers=AUTH).json()

    regenerated = client.post("/api/v1/sessions/today/regenerate", headers=AUTH)
    after = client.get("/api/v1/sessions/today", headers=AUTH).json()

    assert regenerated.status_code == 200
    assert regenerated.json() == after
    assert after["seed"] != before["seed"]
    assert exercise_ids(after) != exercise_ids(before)
    assert after["date"] == before["date"]


def test_regenerate_sin_sesion_previa_la_crea(client, curriculum):
    response = client.post("/api/v1/sessions/today/regenerate", headers=AUTH)

    assert response.status_code == 200
    assert exercise_ids(response.json())


def test_sesion_marca_lo_completado_hoy(client, session, curriculum):
    body = client.get("/api/v1/sessions/today", headers=AUTH).json()
    done_id = exercise_ids(body)[0]
    complete(session, done_id, NOW)

    after = client.get("/api/v1/sessions/today", headers=AUTH).json()

    flags = {
        item["id"]: item["completed_today"] for b in after["blocks"] for item in b["exercises"]
    }
    assert flags[done_id] is True
    assert [flag for key, flag in flags.items() if key != done_id] == [False] * (len(flags) - 1)


def test_sesion_cambia_al_cambiar_el_dia_local(client, clock, curriculum):
    first = client.get("/api/v1/sessions/today", headers=AUTH).json()
    clock.now = NOW + dt.timedelta(days=1)

    tomorrow = client.get("/api/v1/sessions/today", headers=AUTH).json()

    assert first["date"] == "2026-03-10"
    assert tomorrow["date"] == "2026-03-11"


def test_sesion_usa_la_zona_de_settings_para_la_fecha(client, clock, curriculum):
    clock.now = dt.datetime(2026, 3, 10, 2, 0, tzinfo=dt.UTC)  # 23:00 del 9 en Montevideo

    assert client.get("/api/v1/sessions/today", headers=AUTH).json()["date"] == "2026-03-09"


def test_creacion_concurrente_de_la_sesion_usa_la_fila_ganadora(client, session, curriculum):
    from guitarra_api.infra.db.models import PracticeSession
    from guitarra_api.infra.db.repositories.progress import ProgressRepository

    real_get = ProgressRepository.get_practice_session
    calls = {"count": 0}

    def get_then_lose_race(self, day):
        calls["count"] += 1
        found = real_get(self, day)
        if calls["count"] == 1:  # otro request inserta justo después de nuestra lectura
            assert found is None
            session.add(PracticeSession(date=day, seed=7, status="planned", planned=[]))
            session.commit()
        return found

    ProgressRepository.get_practice_session = get_then_lose_race
    try:
        response = client.get("/api/v1/sessions/today", headers=AUTH)
    finally:
        ProgressRepository.get_practice_session = real_get

    assert response.status_code == 200
    assert response.json()["seed"] == 7


def test_sesion_sin_curriculo_devuelve_bloques_vacios(client):
    body = client.get("/api/v1/sessions/today", headers=AUTH).json()

    assert body["blocks"] == []
    assert body["total_minutes"] == 0


# --- reglas de recordatorio -------------------------------------------------


def test_reglas_sin_fila_devuelven_defaults(client):
    response = client.get("/api/v1/reminders/rules", headers=AUTH)

    assert response.json() == {
        "excluded_weekdays": [],
        "inactivity_threshold_days": 3,
        "preferred_window": None,
    }


def test_reglas_se_guardan_y_se_normalizan(client):
    rules = {
        "excluded_weekdays": [6, 0, 6],
        "inactivity_threshold_days": 5,
        "preferred_window": {"start": "19:00", "end": "21:30"},
    }

    put = client.put("/api/v1/reminders/rules", json=rules, headers=AUTH)
    got = client.get("/api/v1/reminders/rules", headers=AUTH)

    assert put.status_code == 200
    assert got.json() == {**rules, "excluded_weekdays": [0, 6]}


def test_reglas_se_pueden_limpiar_la_franja(client):
    base = {"excluded_weekdays": [], "inactivity_threshold_days": 3}
    window = {**base, "preferred_window": {"start": "08:00", "end": "09:00"}}
    client.put("/api/v1/reminders/rules", json=window, headers=AUTH)
    client.put("/api/v1/reminders/rules", json=base, headers=AUTH)

    assert client.get("/api/v1/reminders/rules", headers=AUTH).json()["preferred_window"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"excluded_weekdays": [7]},
        {"excluded_weekdays": [-1]},
        {"excluded_weekdays": ["lunes"]},
        {"inactivity_threshold_days": 0},
        {"inactivity_threshold_days": 366},
        {"preferred_window": {"start": "25:00", "end": "26:00"}},
        {"preferred_window": {"start": "21:00", "end": "19:00"}},
        {"preferred_window": {"start": "19:00"}},
        {"desconocido": 1},
    ],
)
def test_reglas_invalidas_devuelven_422(client, body):
    assert client.put("/api/v1/reminders/rules", json=body, headers=AUTH).status_code == 422
