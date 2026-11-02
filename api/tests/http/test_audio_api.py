"""Subida de audio por el worker y descarga con range requests (ADR 0013)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings
from guitarra_api.infra.db.models import AudioAsset
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.repositories.songs import SongRepository
from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app

UI_TOKEN = "token-ui"
WORKER_TOKEN = "token-worker"
UI = {"Authorization": f"Bearer {UI_TOKEN}"}
WORKER = {"Authorization": f"Bearer {WORKER_TOKEN}"}
M4A = {"Content-Type": "audio/mp4"}
MAX_BYTES = 1000
PAYLOAD = bytes(range(256)) * 2  # 512 bytes distinguibles


@pytest.fixture
def client(session, tmp_path):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_api_settings] = lambda: Settings(
        guitar_api_token=UI_TOKEN,
        guitar_worker_token=WORKER_TOKEN,
        guitar_audio_dir=tmp_path / "audio",
        guitar_audio_max_bytes=MAX_BYTES,
    )
    return TestClient(app)


@pytest.fixture
def ids(session) -> tuple[int, int]:
    """(song_id, job_id) de una canción con su trabajo de análisis."""
    song = SongRepository(session).add_song(
        title="Flaca", artist="Calamaro", source="youtube", youtube_id="abc123"
    )
    job = JobRepository(session).add_job(song.id)
    return song.id, job.id


def upload(client, job_id, data=PAYLOAD, kind="original", headers=None):
    return client.post(
        f"/api/v1/jobs/{job_id}/assets/{kind}",
        content=data,
        headers=headers or {**WORKER, **M4A},
    )


def download(client, song_id, kind="original", **headers):
    return client.get(f"/api/v1/songs/{song_id}/audio/{kind}", headers={**UI, **headers})


def test_sube_y_sirve_completo(client, ids, tmp_path):
    song_id, job_id = ids
    response = upload(client, job_id)
    assert response.status_code == 200
    assert response.json() == {"kind": "original", "format": "m4a", "size": len(PAYLOAD)}
    assert (tmp_path / "audio" / str(song_id) / "original.m4a").read_bytes() == PAYLOAD

    got = download(client, song_id)
    assert got.status_code == 200
    assert got.content == PAYLOAD
    assert got.headers["content-type"] == "audio/mp4"
    assert got.headers["accept-ranges"] == "bytes"
    assert got.headers["content-length"] == str(len(PAYLOAD))


def test_rango_cerrado_devuelve_206(client, ids):
    song_id, job_id = ids
    upload(client, job_id)
    got = download(client, song_id, Range="bytes=0-99")
    assert got.status_code == 206
    assert got.content == PAYLOAD[:100]
    assert got.headers["content-range"] == f"bytes 0-99/{len(PAYLOAD)}"
    assert got.headers["content-length"] == "100"


def test_rango_abierto(client, ids):
    song_id, job_id = ids
    upload(client, job_id)
    got = download(client, song_id, Range="bytes=100-")
    assert got.status_code == 206
    assert got.content == PAYLOAD[100:]
    assert got.headers["content-range"] == f"bytes 100-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"


def test_rango_de_sufijo_y_fin_pasado_del_tamano(client, ids):
    song_id, job_id = ids
    upload(client, job_id)
    assert download(client, song_id, Range="bytes=-10").content == PAYLOAD[-10:]
    got = download(client, song_id, Range="bytes=500-9999")
    assert got.content == PAYLOAD[500:]
    assert got.headers["content-range"] == f"bytes 500-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"


@pytest.mark.parametrize(
    "value", ["bytes=9999-", "bytes=50-10", "bytes=abc", "items=0-5", "bytes=0-1,5-6"]
)
def test_rango_invalido_da_416(client, ids, value):
    song_id, job_id = ids
    upload(client, job_id)
    got = download(client, song_id, Range=value)
    assert got.status_code == 416
    assert got.headers["content-range"] == f"bytes */{len(PAYLOAD)}"


def test_tipo_desconocido_da_422(client, ids):
    song_id, job_id = ids
    assert upload(client, job_id, kind="video").status_code == 422
    assert download(client, song_id, kind="video").status_code == 422


def test_inexistentes_dan_404(client, ids):
    song_id, _ = ids
    assert upload(client, 9999).status_code == 404
    assert download(client, 9999).status_code == 404
    assert download(client, song_id, kind="stem").status_code == 404  # sin subir


def test_si_falta_el_archivo_en_disco_da_404(client, ids, tmp_path):
    song_id, job_id = ids
    upload(client, job_id)
    (tmp_path / "audio" / str(song_id) / "original.m4a").unlink()
    assert download(client, song_id).status_code == 404


def test_el_token_de_la_ui_no_sube_y_el_del_worker_no_descarga(client, ids):
    song_id, job_id = ids
    assert upload(client, job_id, headers={**UI, **M4A}).status_code == 401
    assert upload(client, job_id, headers=M4A).status_code == 401
    upload(client, job_id)
    assert client.get(f"/api/v1/songs/{song_id}/audio/original", headers=WORKER).status_code == 401
    assert client.get(f"/api/v1/songs/{song_id}/audio/original").status_code == 401


def test_descarga_acepta_token_por_query_para_audio_src(client, ids):
    song_id, job_id = ids
    upload(client, job_id)
    url = f"/api/v1/songs/{song_id}/audio/original"
    assert client.get(url, params={"token": UI_TOKEN}).content == PAYLOAD
    assert client.get(url, params={"token": WORKER_TOKEN}).status_code == 401
    assert client.get(url, params={"token": "otro"}).status_code == 401


def test_volver_a_subir_reemplaza(client, session, ids, tmp_path):
    song_id, job_id = ids
    upload(client, job_id, data=PAYLOAD)
    upload(client, job_id, data=b"nuevo")
    assert download(client, song_id).content == b"nuevo"
    assert session.scalar(select(func.count()).select_from(AudioAsset)) == 1
    assert [p.name for p in (tmp_path / "audio" / str(song_id)).iterdir()] == ["original.m4a"]


def test_pasarse_del_tope_da_413_y_no_deja_nada(client, session, ids, tmp_path):
    song_id, job_id = ids
    assert upload(client, job_id, data=b"x" * (MAX_BYTES + 1)).status_code == 413
    assert session.scalar(select(func.count()).select_from(AudioAsset)) == 0
    folder = tmp_path / "audio" / str(song_id)
    assert not folder.exists() or list(folder.iterdir()) == []


def test_413_no_pisa_el_audio_anterior(client, ids):
    song_id, job_id = ids
    upload(client, job_id)
    upload(client, job_id, data=b"x" * (MAX_BYTES + 1))
    assert download(client, song_id).content == PAYLOAD


def test_formato_no_soportado_da_415(client, ids):
    _, job_id = ids
    response = upload(client, job_id, headers={**WORKER, "Content-Type": "audio/ogg"})
    assert response.status_code == 415


def test_cuerpo_vacio_da_422(client, ids):
    _, job_id = ids
    assert upload(client, job_id, data=b"").status_code == 422


def test_el_detalle_de_la_cancion_lista_el_audio(client, ids):
    song_id, job_id = ids
    assert client.get(f"/api/v1/songs/{song_id}", headers=UI).json()["audio"] == []
    upload(client, job_id)
    audio = client.get(f"/api/v1/songs/{song_id}", headers=UI).json()["audio"]
    assert audio == [
        {"kind": "original", "format": "m4a", "url": f"/api/v1/songs/{song_id}/audio/original"}
    ]
