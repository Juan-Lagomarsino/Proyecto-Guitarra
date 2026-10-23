import pytest
from fastapi.testclient import TestClient

from guitarra_api.config import Settings
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.models import AnalysisJob, SongSection
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
YT = "dQw4w9WgXcQ"
SPOTIFY = "4uLU6hMCjMI75M1A2tKUQC"


@pytest.fixture
def client(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(guitar_api_token=TOKEN)
    return TestClient(app)


def post_song(client, body):
    return client.post("/api/v1/songs", json=body, headers=AUTH)


def chart_content(instrument="electric", bpm=96):
    return SongChartContent.model_validate(
        {
            "instrument": instrument,
            "key": {"tonic": "A", "mode": "minor", "confidence": 0.7},
            "bpm": bpm,
            "bpm_confidence": 0.9,
            "time_signature": "4/4",
            "capo": 0,
            "sections": [
                {
                    "id": "intro",
                    "name": "Intro",
                    "start_s": 0,
                    "end_s": 10,
                    "order": 0,
                    "chord_source": "detected",
                    "chords": [
                        {"t_s": 1.0, "name": "Am", "shape": ["x", 0, 2, 2, 1, 0], "confidence": 0.9}
                    ],
                }
            ],
            "sources": [],
        }
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/songs"),
        ("post", "/api/v1/songs"),
        ("get", "/api/v1/songs/1"),
        ("get", "/api/v1/songs/1/chart?instrument=electric"),
        ("post", "/api/v1/songs/1/reanalyze"),
    ],
)
def test_requiere_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_alta_por_link_de_youtube(client, session):
    response = post_song(client, {"url": f"https://youtu.be/{YT}?si=x"})
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "youtube"
    assert (body["title"], body["artist"]) == (None, None)
    assert body["analysis_status"] == "queued"
    jobs = session.query(AnalysisJob).all()
    assert [(job.song_id, job.type, job.status) for job in jobs] == [
        (body["id"], "analyze", "queued")
    ]


def test_alta_por_link_de_spotify(client):
    response = post_song(
        client, {"url": f"https://open.spotify.com/intl-es/track/{SPOTIFY}?si=abc"}
    )
    assert response.status_code == 201
    assert response.json()["source"] == "spotify"


def test_alta_por_nombre(client):
    response = post_song(client, {"title": "Wonderwall", "artist": "Oasis"})
    assert response.status_code == 201
    body = response.json()
    assert (body["source"], body["title"], body["artist"]) == ("search", "Wonderwall", "Oasis")
    assert body["analysis_status"] == "queued"


def test_idempotente_con_dos_formas_de_link(client, session):
    first = post_song(client, {"url": f"https://www.youtube.com/watch?v={YT}&t=3"})
    second = post_song(client, {"url": f"https://youtu.be/{YT}"})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get("/api/v1/songs", headers=AUTH).json()) == 1
    assert session.query(AnalysisJob).count() == 1


def test_idempotente_por_spotify(client, session):
    first = post_song(client, {"url": f"https://open.spotify.com/track/{SPOTIFY}"})
    second = post_song(client, {"url": f"https://open.spotify.com/intl-es/track/{SPOTIFY}?si=z"})
    assert (first.status_code, second.status_code) == (201, 200)
    assert session.query(AnalysisJob).count() == 1


def test_idempotente_por_nombre_normalizado(client, session):
    first = post_song(client, {"title": "Canción Animal", "artist": "Soda Stereo"})
    second = post_song(client, {"title": "  cancion   animal ", "artist": "SODA STEREO"})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert session.query(AnalysisJob).count() == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"url": f"https://youtu.be/{YT}", "title": "A", "artist": "B"},
        {"title": "Solo título"},
        {"artist": "Solo artista"},
        {"title": " ", "artist": "B"},
        {"url": "https://example.com/algo"},
        {"url": "https://[abc"},
        {"url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"},
    ],
)
def test_alta_invalida_da_422(client, body):
    assert post_song(client, body).status_code == 422


def test_lista_mas_reciente_primero_con_paso_actual(client, session):
    old = post_song(client, {"title": "Vieja", "artist": "A"}).json()
    new = post_song(client, {"title": "Nueva", "artist": "B"}).json()
    job = session.query(AnalysisJob).filter_by(song_id=new["id"]).one()
    job.status, job.current_step = "running", "tempo"
    session.commit()
    body = client.get("/api/v1/songs", headers=AUTH).json()
    assert [item["id"] for item in body] == [new["id"], old["id"]]
    assert body[0]["current_step"] == "tempo"
    assert body[1]["current_step"] is None
    assert set(body[0]) == {
        "id", "title", "artist", "source", "analysis_status", "current_step", "bpm", "key",
        "created_at",
    }  # fmt: skip


def test_detalle(client, session):
    created = post_song(client, {"url": f"https://youtu.be/{YT}"}).json()
    song = SongRepository(session).get(created["id"])
    song.duration_s, song.year, song.bpm, song.key = 215.5, 1987, 113.0, "A minor"
    song.sections = [SongSection(slug="intro", name="Intro", start_s=0, end_s=10, position=0)]
    job = session.query(AnalysisJob).one()
    job.status, job.error = "error", "yt-dlp falló"
    song.analysis_status = "error"
    session.commit()
    body = client.get(f"/api/v1/songs/{created['id']}", headers=AUTH).json()
    assert body["url"] == f"https://youtu.be/{YT}"
    assert (body["duration_s"], body["year"], body["bpm"], body["key"]) == (
        215.5, 1987, 113.0, "A minor",
    )  # fmt: skip
    assert body["error"] == "yt-dlp falló"
    assert body["analysis_status"] == "error"
    assert body["sections"] == [
        {"slug": "intro", "name": "Intro", "start_s": 0, "end_s": 10, "position": 0}
    ]


def test_detalle_inexistente_da_404(client):
    assert client.get("/api/v1/songs/999", headers=AUTH).status_code == 404


def test_chart_del_usuario_gana_sobre_auto_posterior(client, session):
    song_id = post_song(client, {"title": "T", "artist": "A"}).json()["id"]
    repo = SongRepository(session)
    repo.add_chart(song_id, "auto", chart_content(bpm=90))
    repo.add_chart(song_id, "user", chart_content(bpm=100))
    repo.add_chart(song_id, "auto", chart_content(bpm=110))
    response = client.get(f"/api/v1/songs/{song_id}/chart?instrument=electric", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert (body["origin"], body["version"], body["content"]["bpm"]) == ("user", 2, 100)
    assert set(body) >= {"content", "version", "origin", "confidence", "created_at"}


def test_chart_sin_datos_da_404_con_mensaje(client, session):
    song_id = post_song(client, {"title": "T", "artist": "A"}).json()["id"]
    SongRepository(session).add_chart(song_id, "auto", chart_content("electric"))
    response = client.get(f"/api/v1/songs/{song_id}/chart?instrument=classical", headers=AUTH)
    assert response.status_code == 404
    assert "classical" in response.json()["detail"]


def test_chart_de_cancion_inexistente_da_404(client):
    response = client.get("/api/v1/songs/999/chart?instrument=electric", headers=AUTH)
    assert response.status_code == 404


@pytest.mark.parametrize("query", ["", "?instrument=bajo"])
def test_chart_instrumento_invalido_da_422(client, query):
    assert client.get(f"/api/v1/songs/1/chart{query}", headers=AUTH).status_code == 422


def test_reanalizar_encola_un_trabajo_nuevo(client, session):
    song_id = post_song(client, {"title": "T", "artist": "A"}).json()["id"]
    job = session.query(AnalysisJob).one()
    job.status = "done"
    SongRepository(session).get(song_id).analysis_status = "ready"
    session.commit()
    response = client.post(f"/api/v1/songs/{song_id}/reanalyze", headers=AUTH)
    assert response.status_code == 202
    assert response.json()["analysis_status"] == "queued"
    assert session.query(AnalysisJob).filter_by(status="queued").count() == 1


def test_reanalizar_con_trabajo_activo_da_409(client, session):
    song_id = post_song(client, {"title": "T", "artist": "A"}).json()["id"]
    assert client.post(f"/api/v1/songs/{song_id}/reanalyze", headers=AUTH).status_code == 409
    assert session.query(AnalysisJob).count() == 1


def test_reanalizar_inexistente_da_404(client):
    assert client.post("/api/v1/songs/999/reanalyze", headers=AUTH).status_code == 404


def test_si_encolar_falla_no_queda_la_cancion(client, session, monkeypatch):
    def boom(self, song_id):
        raise RuntimeError("cola caída")

    monkeypatch.setattr(SongRepository, "stage_job", boom)
    with pytest.raises(RuntimeError):
        post_song(client, {"url": f"https://youtu.be/{YT}"})
    with pytest.raises(RuntimeError):
        post_song(client, {"title": "T", "artist": "A"})
    assert SongRepository(session).list_songs() == []
    assert session.query(AnalysisJob).count() == 0


def test_busqueda_por_nombre_tolera_canciones_sin_titulo(client):
    post_song(client, {"url": f"https://youtu.be/{YT}"})
    response = post_song(client, {"title": "T", "artist": "A"})
    assert response.status_code == 201
