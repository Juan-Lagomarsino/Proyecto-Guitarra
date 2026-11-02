import httpx
import pytest

from conftest import JOB, FakeApi
from guitarra_worker.api_client import ApiClient, ApiError, LeaseLostError


def test_claim_manda_token_y_devuelve_job(make_client):
    api = FakeApi([JOB])
    job = make_client(api).claim()
    assert job.job_id == 7 and job.youtube_id == "abc123"
    assert api.calls[0] == ("/api/v1/jobs/claim", {"worker_id": "w1"}, "Bearer tok")


def test_claim_204_es_none(make_client):
    assert make_client(FakeApi()).claim() is None


def test_heartbeat_409_lanza_lease_perdido(make_client):
    with pytest.raises(LeaseLostError):
        make_client(FakeApi(heartbeat_status=409)).heartbeat(7, "tempo")


def test_reintenta_errores_de_red_y_luego_funciona():
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) < 3:
            raise httpx.ConnectError("caído")
        return httpx.Response(204)

    client = ApiClient(
        "http://api", "t", "w", transport=httpx.MockTransport(handler), sleep=lambda s: None
    )
    assert client.claim() is None
    assert len(attempts) == 3


def test_reintentos_acotados():
    def handler(request):
        raise httpx.ConnectError("caído")

    client = ApiClient(
        "http://api",
        "t",
        "w",
        transport=httpx.MockTransport(handler),
        retries=2,
        sleep=lambda s: None,
    )
    with pytest.raises(ApiError):
        client.claim()


def test_result_y_fail_incluyen_worker_id(make_client):
    api = FakeApi()
    client = make_client(api)
    client.send_result(7, {"metadata": {}, "sections": [], "charts": []})
    client.fail(7, "boom", True)
    assert api.paths("/result")[0][1]["worker_id"] == "w1"
    assert api.paths("/fail")[0][1] == {"worker_id": "w1", "error": "boom", "retryable": True}


def test_fail_trunca_el_error_y_es_reintentable_por_defecto(make_client):
    api = FakeApi()
    make_client(api).fail(7, "x" * 5000)
    body = api.paths("/fail")[0][1]
    assert len(body["error"]) == 4000 and body["retryable"] is True


def _upload_client(handler):
    return ApiClient(
        "http://api", "tok", "w1", transport=httpx.MockTransport(handler), sleep=lambda s: None
    )


def test_upload_asset_manda_cuerpo_crudo_con_headers(tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"x" * 300_000)
    seen = {}

    def handler(request):
        seen["method"], seen["path"] = request.method, request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["type"] = request.headers["content-type"]
        seen["body"] = b"".join(request.stream)
        return httpx.Response(200)

    _upload_client(handler).upload_asset(7, "original", audio)
    assert seen["method"] == "POST" and seen["path"] == "/api/v1/jobs/7/assets/original"
    assert seen["auth"] == "Bearer tok" and seen["type"] == "audio/mp4"
    assert seen["body"] == audio.read_bytes()


def test_upload_asset_es_streaming(tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"y" * 500_000)
    chunks = []

    class RecordingTransport(httpx.BaseTransport):
        def handle_request(self, request):  # MockTransport lee el cuerpo entero antes de llamar
            chunks.extend(len(c) for c in request.stream)
            return httpx.Response(200)

    client = ApiClient("http://api", "tok", "w1", transport=RecordingTransport())
    client.upload_asset(7, "original", audio)
    assert len(chunks) > 1 and max(chunks) < 500_000


def test_upload_asset_reintenta_5xx_y_reabre_el_archivo(tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"z" * 1000)
    bodies = []

    def handler(request):
        bodies.append(b"".join(request.stream))
        return httpx.Response(503 if len(bodies) == 1 else 200)

    _upload_client(handler).upload_asset(7, "original", audio)
    assert bodies == [audio.read_bytes()] * 2


def test_upload_asset_409_es_lease_perdido(tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"z")
    with pytest.raises(LeaseLostError):
        _upload_client(lambda r: httpx.Response(409)).upload_asset(7, "original", audio)


def test_upload_asset_4xx_lleva_status(tmp_path):
    audio = tmp_path / "a.m4a"
    audio.write_bytes(b"z")
    with pytest.raises(ApiError) as info:
        _upload_client(lambda r: httpx.Response(413)).upload_asset(7, "original", audio)
    assert info.value.status_code == 413
