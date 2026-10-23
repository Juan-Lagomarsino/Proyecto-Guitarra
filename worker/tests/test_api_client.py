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
