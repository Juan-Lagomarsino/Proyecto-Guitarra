"""API de la cola de trabajos (Postgres de testcontainers; el worker usa su propio token)."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.http.clock import get_clock
from guitarra_api.infra.db.models import (
    AnalysisJob,
    AudioAsset,
    Exercise,
    ExerciseCompletion,
    Song,
    SongChart,
    SongSection,
)
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app
from test_songs_db import chart_content

UI_TOKEN = "token-ui"
WORKER_TOKEN = "token-worker"
WORKER = {"Authorization": f"Bearer {WORKER_TOKEN}"}
LEASE = 300
T0 = dt.datetime(2026, 10, 1, 12, 0, tzinfo=dt.UTC)


class FakeClock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += dt.timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(session, clock):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        guitar_api_token=UI_TOKEN, guitar_worker_token=WORKER_TOKEN, guitar_job_lease_seconds=LEASE
    )
    return TestClient(app)


@pytest.fixture
def songs(session) -> SongRepository:
    return SongRepository(session)


@pytest.fixture
def jobs(session) -> JobRepository:
    return JobRepository(session)


def new_song(songs, youtube_id="abc123", title="Flaca") -> Song:
    return songs.add_song(title=title, artist="Calamaro", source="youtube", youtube_id=youtube_id)


def claim(client, worker="w1"):
    return client.post("/api/v1/jobs/claim", json={"worker_id": worker}, headers=WORKER)


def chart_json(instrument="electric", ids=("intro",)) -> dict:
    content = chart_content(instrument).model_dump(mode="json", exclude_none=True)
    base = content["sections"][0]
    content["sections"] = [
        {**base, "id": slug, "order": index, "start_s": index * 10, "end_s": index * 10 + 10,
         "chords": [{**base["chords"][0], "t_s": index * 10 + 1}]}
        for index, slug in enumerate(ids)
    ]  # fmt: skip
    return content


def result_body(worker="w1", ids=("intro",), charts=None, **metadata) -> dict:
    return {
        "worker_id": worker,
        "metadata": {"bpm": 98.5, "key": "A minor", "duration_s": 200.0, "year": 1997, **metadata},
        "sections": [
            {"slug": slug, "name": slug.title(), "start_s": i * 10, "end_s": i * 10 + 10,
             "position": i}
            for i, slug in enumerate(ids)
        ],
        "charts": charts if charts is not None else [chart_json("electric", ids)],
    }  # fmt: skip


# --- auth --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/jobs/claim"), ("post", "/jobs/1/heartbeat"), ("post", "/jobs/1/fail")],
)
def test_jobs_rechaza_el_token_de_la_ui_y_la_ausencia_de_token(client, method, path):
    body = {"worker_id": "w1", "error": "x"}
    ui = {"Authorization": f"Bearer {UI_TOKEN}"}
    assert getattr(client, method)(f"/api/v1{path}", json=body, headers=ui).status_code == 401
    assert getattr(client, method)(f"/api/v1{path}", json=body).status_code == 401


def test_result_rechaza_el_token_de_la_ui(client):
    ui = {"Authorization": f"Bearer {UI_TOKEN}"}
    assert client.post("/api/v1/jobs/1/result", json=result_body(), headers=ui).status_code == 401


def test_el_token_del_worker_no_sirve_en_el_resto_de_la_api(client):
    assert client.get("/api/v1/settings", headers=WORKER).status_code == 401
    assert client.get("/api/v1/levels", headers=WORKER).status_code == 401


def test_sin_token_de_worker_configurado_jobs_rechaza_todo(client):
    client.app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=UI_TOKEN)
    response = client.post("/api/v1/jobs/claim", json={"worker_id": "w"}, headers=WORKER)
    assert response.status_code == 401
    assert client.post("/api/v1/jobs/claim", json={"worker_id": "w"}).status_code == 401


# --- claim -------------------------------------------------------------------------------


def test_claim_sin_trabajos_devuelve_204(client):
    response = claim(client)
    assert response.status_code == 204
    assert response.content == b""


def test_claim_entrega_el_trabajo_mas_viejo_y_marca_la_cancion(client, songs, jobs, session):
    first = new_song(songs, "v1", "Primera")
    second = new_song(songs, "v2", "Segunda")
    jobs.add_job(first.id)
    jobs.add_job(second.id)

    response = claim(client)

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "job_id": 1,
        "job_type": "analyze",
        "song_id": first.id,
        "title": "Primera",
        "artist": "Calamaro",
        "source": "youtube",
        "url": None,
        "youtube_id": "v1",
        "spotify_id": None,
        "attempt": 1,
        "max_attempts": 3,
        "cifra_text": None,
        "lease_until": "2026-10-01T12:05:00Z",
        "chord_shape_preferences": {},
        "fingering_preferences": {"positions": {}, "zones": {}},
        "chart": None,
    }
    job = session.get(AnalysisJob, 1)
    assert (job.status, job.claimed_by, job.attempts) == ("running", "w1", 1)
    assert session.get(Song, first.id).analysis_status == "processing"
    assert claim(client, "w2").json()["job_id"] == 2
    assert claim(client, "w3").status_code == 204


def test_claim_lleva_el_texto_de_la_cifra(client, songs, jobs, session):
    song = new_song(songs)
    song.cifra_text = "[Intro]\nAm G"
    session.commit()
    jobs.add_job(song.id)
    assert claim(client).json()["cifra_text"] == "[Intro]\nAm G"


def test_lease_vencido_vuelve_a_la_cola(client, songs, jobs, clock):
    jobs.add_job(new_song(songs).id)
    assert claim(client, "w1").json()["attempt"] == 1

    clock.advance(LEASE - 1)
    assert claim(client, "w2").status_code == 204  # todavía vigente

    clock.advance(2)
    retaken = claim(client, "w2")
    assert retaken.status_code == 200
    assert retaken.json()["attempt"] == 2


def test_lease_vencido_con_intentos_agotados_pasa_a_error(client, songs, jobs, session, clock):
    song = new_song(songs)
    jobs.add_job(song.id, max_attempts=1)
    claim(client, "w1")

    clock.advance(LEASE + 1)

    assert claim(client, "w2").status_code == 204
    job = session.get(AnalysisJob, 1)
    assert job.status == "error"
    assert job.finished_at is not None
    assert job.error
    assert session.get(Song, song.id).analysis_status == "error"


# --- heartbeat ---------------------------------------------------------------------------


def test_heartbeat_extiende_el_lease_y_guarda_el_paso(client, songs, jobs, session, clock):
    jobs.add_job(new_song(songs).id)
    claim(client)
    clock.advance(200)

    response = client.post(
        "/api/v1/jobs/1/heartbeat",
        json={"worker_id": "w1", "current_step": "tempo"},
        headers=WORKER,
    )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": 1,
        "status": "running",
        "lease_until": "2026-10-01T12:08:20Z",
    }
    assert session.get(AnalysisJob, 1).current_step == "tempo"


def test_heartbeat_de_otro_worker_da_409(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    claim(client, "w1")
    response = client.post("/api/v1/jobs/1/heartbeat", json={"worker_id": "w2"}, headers=WORKER)
    assert response.status_code == 409


def test_heartbeat_de_un_job_que_no_esta_running_da_409(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    response = client.post("/api/v1/jobs/1/heartbeat", json={"worker_id": "w1"}, headers=WORKER)
    assert response.status_code == 409


def test_heartbeat_de_un_job_inexistente_da_404(client):
    response = client.post("/api/v1/jobs/99/heartbeat", json={"worker_id": "w1"}, headers=WORKER)
    assert response.status_code == 404


# --- result ------------------------------------------------------------------------------


def test_result_valido_guarda_todo_y_marca_done_y_ready(client, songs, jobs, session):
    song = new_song(songs)
    songs.add_chart(song.id, "user", chart_content("electric"))  # versión 1, del usuario
    jobs.add_job(song.id)
    claim(client)
    body = result_body(
        ids=("intro", "verso"),
        charts=[chart_json(i, ("intro", "verso")) for i in ("electric", "classical")],
        title="Flaca (remaster)",
        artist="Andrés Calamaro",
        youtube_id="nuevo123",
    )  # fmt: skip

    response = client.post("/api/v1/jobs/1/result", json=body, headers=WORKER)

    assert response.status_code == 200
    assert response.json() == {"job_id": 1, "status": "done"}
    session.expire_all()
    job = session.get(AnalysisJob, 1)
    assert job.status == "done"
    assert job.finished_at == T0
    song = session.get(Song, song.id)
    assert song.analysis_status == "ready"
    assert (song.bpm, song.key, song.duration_s, song.year) == (98.5, "A minor", 200.0, 1997)
    assert (song.title, song.artist, song.youtube_id) == (
        "Flaca (remaster)",
        "Andrés Calamaro",
        "nuevo123",
    )
    sections = session.scalars(select(SongSection).order_by(SongSection.position)).all()
    assert [(s.slug, s.name, s.position) for s in sections] == [
        ("intro", "Intro", 0),
        ("verso", "Verso", 1),
    ]
    charts = session.scalars(select(SongChart).order_by(SongChart.id)).all()
    assert [(c.instrument, c.version, c.origin) for c in charts] == [
        ("electric", 1, "user"),
        ("electric", 2, "auto"),
        ("classical", 1, "auto"),
    ]
    assert songs.current_chart(song.id, "electric").origin == "user"


def test_result_reemplaza_las_secciones_anteriores(client, songs, jobs, session):
    song = new_song(songs)
    session.add(
        SongSection(song_id=song.id, slug="viejo", name="Viejo", start_s=0, end_s=5, position=0)
    )
    session.commit()
    jobs.add_job(song.id)
    claim(client)

    assert (
        client.post("/api/v1/jobs/1/result", json=result_body(), headers=WORKER).status_code == 200
    )

    session.expire_all()
    assert [s.slug for s in session.scalars(select(SongSection))] == ["intro"]


def test_result_con_chart_invalido_da_422_sin_cambios(client, songs, jobs, session):
    song = new_song(songs)
    jobs.add_job(song.id)
    claim(client)
    bad = chart_json("electric")
    bad["bpm"] = -3

    response = client.post("/api/v1/jobs/1/result", json=result_body(charts=[bad]), headers=WORKER)

    assert response.status_code == 422
    session.expire_all()
    assert session.get(AnalysisJob, 1).status == "running"
    assert session.get(Song, song.id).analysis_status == "processing"
    assert session.scalar(select(func.count()).select_from(SongChart)) == 0
    assert session.scalar(select(func.count()).select_from(SongSection)) == 0


def test_result_con_secciones_del_chart_distintas_a_las_del_body_da_422(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    claim(client)
    body = result_body(ids=("intro",), charts=[chart_json("electric", ("otra",))])
    assert client.post("/api/v1/jobs/1/result", json=body, headers=WORKER).status_code == 422


def test_result_con_dos_charts_del_mismo_instrumento_da_422(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    claim(client)
    body = result_body(charts=[chart_json("electric"), chart_json("electric")])
    assert client.post("/api/v1/jobs/1/result", json=body, headers=WORKER).status_code == 422


def test_result_de_otro_worker_da_409_y_no_cambia_nada(client, songs, jobs, session):
    jobs.add_job(new_song(songs).id)
    claim(client, "w1")
    response = client.post("/api/v1/jobs/1/result", json=result_body("w2"), headers=WORKER)
    assert response.status_code == 409
    assert session.scalar(select(func.count()).select_from(SongChart)) == 0


def test_result_con_youtube_id_de_otra_cancion_da_409_sin_cambios(client, songs, jobs, session):
    new_song(songs, "ocupado", "Otra")
    song = new_song(songs, "v2", "Flaca")
    jobs.add_job(song.id)
    claim(client)

    response = client.post(
        "/api/v1/jobs/1/result", json=result_body(youtube_id="ocupado"), headers=WORKER
    )

    assert response.status_code == 409
    assert "ocupado" in response.json()["detail"]
    session.expire_all()
    assert session.get(AnalysisJob, 1).status == "running"
    assert session.scalar(select(func.count()).select_from(SongChart)) == 0
    assert session.get(Song, song.id).youtube_id == "v2"


# --- fail --------------------------------------------------------------------------------


def fail(client, worker="w1", retryable=True, error="se cayó yt-dlp"):
    body = {"worker_id": worker, "error": error, "retryable": retryable}
    return client.post("/api/v1/jobs/1/fail", json=body, headers=WORKER)


def test_fail_reintentable_vuelve_a_la_cola_y_libera_el_lease(client, songs, jobs, session):
    song = new_song(songs)
    jobs.add_job(song.id)
    claim(client)

    response = fail(client)

    assert response.json() == {"job_id": 1, "status": "queued"}
    session.expire_all()
    job = session.get(AnalysisJob, 1)
    assert (job.claimed_by, job.lease_until, job.error) == (None, None, "se cayó yt-dlp")
    assert session.get(Song, song.id).analysis_status == "queued"
    assert claim(client, "w2").json()["attempt"] == 2


def test_fail_reintentable_sin_intentos_restantes_queda_en_error(client, songs, jobs, session):
    song = new_song(songs)
    jobs.add_job(song.id, max_attempts=1)
    claim(client)

    assert fail(client).json()["status"] == "error"
    assert session.get(Song, song.id).analysis_status == "error"


def test_fail_no_reintentable_queda_en_error(client, songs, jobs, session):
    song = new_song(songs)
    jobs.add_job(song.id)
    claim(client)

    assert fail(client, retryable=False, error="video privado").json()["status"] == "error"

    session.expire_all()
    job = session.get(AnalysisJob, 1)
    assert (job.status, job.error) == ("error", "video privado")
    assert job.finished_at == T0
    assert session.get(Song, song.id).analysis_status == "error"
    assert claim(client, "w2").status_code == 204


def test_fail_de_otro_worker_da_409(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    claim(client, "w1")
    assert fail(client, "w2").status_code == 409


def test_esquemas_de_jobs_en_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/jobs/claim",
        "/api/v1/jobs/{job_id}/heartbeat",
        "/api/v1/jobs/{job_id}/result",
        "/api/v1/jobs/{job_id}/fail",
    } <= set(paths)


def test_claim_de_una_cancion_sin_titulo_ni_artista(client, songs, jobs):
    song = songs.add_song(title=None, artist=None, source="youtube", youtube_id="solo-link")
    jobs.add_job(song.id)

    data = claim(client).json()

    assert (data["title"], data["artist"], data["youtube_id"]) == (None, None, "solo-link")


def test_reanalisis_actualiza_secciones_y_conserva_las_que_tienen_ejercicios(
    client, songs, jobs, session
):
    song = new_song(songs)
    jobs.add_job(song.id)
    claim(client)
    ids = ("intro", "verso", "coro")
    first = client.post("/api/v1/jobs/1/result", json=result_body(ids=ids), headers=WORKER)
    assert first.status_code == 200
    section_ids = {s.slug: s.id for s in session.scalars(select(SongSection))}
    exercise = Exercise(
        song_section_id=section_ids["verso"], slug="verso-ej", title="Verso", type="scale",
        instrument="electric", notation={"version": 1}, bpm_start=60, bpm_target=100,
        duration_min=5, category="technique",
    )  # fmt: skip
    session.add(exercise)
    session.flush()
    session.add(ExerciseCompletion(exercise_id=exercise.id, bpm_achieved=80, instrument="electric"))
    session.commit()

    jobs.add_job(song.id)
    claim(client)
    again = result_body(ids=("intro", "puente"), bpm=120.0)
    assert client.post("/api/v1/jobs/3/result", json=again, headers=WORKER).status_code == 200

    session.expire_all()
    by_slug = {s.slug: s for s in session.scalars(select(SongSection))}
    assert set(by_slug) == {"intro", "verso", "puente"}  # "coro" se borró, "verso" sobrevive
    assert by_slug["intro"].id == section_ids["intro"]
    assert (by_slug["verso"].stale, by_slug["intro"].stale, by_slug["puente"].stale) == (
        True,
        False,
        False,
    )
    assert by_slug["puente"].position == 1
    assert session.scalar(select(func.count()).select_from(ExerciseCompletion)) == 1


# --- separación (F3-T04) -----------------------------------------------------------------

UI = {"Authorization": f"Bearer {UI_TOKEN}"}


def separation_jobs(session) -> list[AnalysisJob]:
    session.expire_all()
    return list(
        session.scalars(
            select(AnalysisJob).where(AnalysisJob.type == "separation").order_by(AnalysisJob.id)
        )
    )


def finish_analysis(client, songs, jobs, worker="w1"):
    song = new_song(songs)
    jobs.add_job(song.id)
    claimed = claim(client, worker).json()
    response = client.post(
        f"/api/v1/jobs/{claimed['job_id']}/result", json=result_body(worker), headers=WORKER
    )
    assert response.status_code == 200
    return song


def separation_status(client, song_id) -> str:
    return client.get(f"/api/v1/songs/{song_id}", headers=UI).json()["separation_status"]


def post_result(client, job_id, body):
    return client.post(f"/api/v1/jobs/{job_id}/result", json=body, headers=WORKER)


def test_el_resultado_de_un_analisis_encola_una_separacion(client, songs, jobs, session):
    song = finish_analysis(client, songs, jobs)

    queued = separation_jobs(session)

    assert [(j.song_id, j.status, j.max_attempts) for j in queued] == [(song.id, "queued", 3)]
    session.refresh(song)
    assert song.analysis_status == "ready"  # la separación no toca el estado del análisis


def test_un_reanalisis_con_separacion_activa_no_encola_otra(client, songs, jobs, session):
    song = finish_analysis(client, songs, jobs)
    jobs.add_job(song.id)  # reanálisis; la separación sigue en cola
    first = claim(client, "w1").json()
    assert first["job_type"] == "analyze"
    post_result(client, first["job_id"], result_body())

    assert len(separation_jobs(session)) == 1


def test_con_pista_sin_guitarra_no_se_encola_separacion(client, songs, jobs, session):
    song = new_song(songs)
    session.add(AudioAsset(song_id=song.id, kind="no_guitar", path="x.m4a", format="m4a"))
    session.commit()
    jobs.add_job(song.id)
    claimed = claim(client).json()

    post_result(client, claimed["job_id"], result_body())

    assert separation_jobs(session) == []
    assert separation_status(client, song.id) == "done"


def test_reanalisis_tras_separar_no_re_encola(client, songs, jobs, session):
    song = finish_analysis(client, songs, jobs)
    sep = claim(client).json()
    assert sep["job_type"] == "separation"
    session.add(AudioAsset(song_id=song.id, kind="no_guitar", path="x.m4a", format="m4a"))
    session.commit()
    post_result(client, sep["job_id"], {"worker_id": "w1"})
    jobs.add_job(song.id)
    again = claim(client).json()
    post_result(client, again["job_id"], result_body())

    assert len(separation_jobs(session)) == 1


def test_claim_devuelve_el_tipo_y_los_datos_de_la_separacion(client, songs, jobs):
    song = finish_analysis(client, songs, jobs)

    data = claim(client, "w2").json()

    assert data["job_type"] == "separation"
    assert (data["song_id"], data["youtube_id"], data["title"], data["artist"]) == (
        song.id,
        "abc123",
        "Flaca",
        "Calamaro",
    )
    assert data["attempt"] == 1


def test_claim_de_un_analisis_dice_analyze(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    assert claim(client).json()["job_type"] == "analyze"


def test_claim_prioriza_el_analisis_sobre_la_separacion(client, songs, jobs, clock):
    finish_analysis(client, songs, jobs)  # deja una separación en cola
    clock.advance(10)
    jobs.add_job(new_song(songs, youtube_id="otro", title="Otra").id)

    assert claim(client).json()["job_type"] == "analyze"
    assert claim(client).json()["job_type"] == "separation"


def test_result_de_separacion_sin_chart_la_marca_hecha(client, songs, jobs, session):
    song = finish_analysis(client, songs, jobs)
    sep = claim(client).json()

    response = post_result(client, sep["job_id"], {"worker_id": "w1"})

    assert response.json() == {"job_id": sep["job_id"], "status": "done"}
    assert separation_jobs(session)[0].status == "done"
    assert separation_status(client, song.id) == "done"


def test_result_con_cuerpo_de_otro_tipo_da_422(client, songs, jobs):
    finish_analysis(client, songs, jobs)
    sep = claim(client).json()
    assert post_result(client, sep["job_id"], result_body()).status_code == 422

    jobs.add_job(new_song(songs, "otro", "Otra").id)
    analysis = claim(client).json()
    assert analysis["job_type"] == "analyze"
    assert post_result(client, analysis["job_id"], {"worker_id": "w1"}).status_code == 422


def test_separacion_no_cambia_el_estado_de_analisis_de_la_cancion(client, songs, jobs, session):
    song = finish_analysis(client, songs, jobs)
    sep = claim(client).json()
    session.refresh(song)
    assert song.analysis_status == "ready"
    client.post(
        f"/api/v1/jobs/{sep['job_id']}/fail",
        json={"worker_id": "w1", "error": "boom"},
        headers=WORKER,
    )
    session.refresh(song)
    assert song.analysis_status == "ready"


def test_separacion_reintenta_hasta_el_tope_y_queda_en_error(client, songs, jobs):
    song = finish_analysis(client, songs, jobs)
    for attempt in (1, 2, 3):
        data = claim(client).json()
        assert (data["job_type"], data["attempt"]) == ("separation", attempt)
        assert separation_status(client, song.id) == "running"
        response = client.post(
            f"/api/v1/jobs/{data['job_id']}/fail",
            json={"worker_id": "w1", "error": "demucs"},
            headers=WORKER,
        )
    assert response.json()["status"] == "error"
    assert claim(client).status_code == 204
    assert separation_status(client, song.id) == "error"
    # el error de la separación no se mezcla con el del análisis
    detail = client.get(f"/api/v1/songs/{song.id}", headers=UI).json()
    assert detail["error"] is None
    assert detail["analysis_status"] == "ready"


def test_separacion_con_lease_vencido_se_reclama_y_agota_intentos(client, songs, jobs, clock):
    finish_analysis(client, songs, jobs)
    for _ in range(3):
        assert claim(client).json()["job_type"] == "separation"
        clock.advance(LEASE + 1)
    assert claim(client).status_code == 204


def test_separation_status_none_queued_running(client, songs, jobs):
    song = new_song(songs)
    assert separation_status(client, song.id) == "none"
    jobs.add_job(song.id)
    claim(client)
    post_result(client, 1, result_body())
    assert separation_status(client, song.id) == "queued"
    claim(client)
    assert separation_status(client, song.id) == "running"


def test_la_separacion_activa_no_bloquea_el_reanalisis(client, songs, jobs):
    song = finish_analysis(client, songs, jobs)  # separación en cola
    response = client.post(f"/api/v1/songs/{song.id}/reanalyze", headers=UI)
    assert response.status_code in (200, 202)
    assert response.json()["analysis_status"] == "queued"
