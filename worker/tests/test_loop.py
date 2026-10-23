import pytest

from conftest import JOB, FakeApi
from guitarra_worker.api_client import ApiError, Job
from guitarra_worker.config import Settings
from guitarra_worker.loop import process_job, run_loop
from guitarra_worker.pipeline.step import RetryableStepError


class Step:
    version = "1"

    def __init__(self, name="s", error=None):
        self.name, self.error = name, error

    def run(self, ctx):
        if self.error:
            raise self.error
        return {"metadata": {"bpm": 90}, "sections": [], "charts": []}


def assemble(outputs):
    return outputs["s"]


def no_sleep(seconds):
    pytest.fail("no debía dormir")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None, cache_dir=tmp_path / "cache", poll_interval_s=1, max_backoff_s=5
    )


def test_exito_manda_result(make_client, job, tmp_path):
    api = FakeApi()
    assert process_job(make_client(api), job, [Step()], assemble, tmp_path, 60)
    ((_, body, _),) = api.paths("/result")
    assert body["metadata"] == {"bpm": 90} and body["worker_id"] == "w1"


@pytest.mark.parametrize(
    ("error", "retryable"),
    [(RetryableStepError("timeout"), True), (ValueError("mal"), False)],
)
def test_paso_que_falla_manda_fail(make_client, job, tmp_path, error, retryable):
    api = FakeApi()
    assert not process_job(make_client(api), job, [Step(error=error)], assemble, tmp_path, 60)
    ((_, body, _),) = api.paths("/fail")
    assert body["retryable"] is retryable
    assert str(error) in body["error"]
    assert not api.paths("/result")


def test_heartbeat_409_aborta_sin_result_ni_fail(make_client, job, tmp_path):
    api = FakeApi(heartbeat_status=409)
    assert not process_job(make_client(api), job, [Step()], assemble, tmp_path, 60)
    assert not api.paths("/result") and not api.paths("/fail")


def test_sin_trabajo_backoff_exponencial_con_tope(make_client, settings):
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 5:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_loop(make_client(FakeApi()), settings, [Step()], assemble, sleep=sleep)
    assert sleeps == [1, 2, 4, 5, 5]


def test_backoff_se_reinicia_tras_un_trabajo(make_client, settings):
    claims = iter([None, None, Job.model_validate(JOB), None])
    client = make_client(FakeApi())
    client.claim = lambda: next(claims)
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_loop(client, settings, [Step()], assemble, sleep=sleep)
    assert sleeps == [1, 2, 1]


def test_once_procesa_un_trabajo_y_sale(make_client, settings):
    api = FakeApi([JOB, JOB])
    run_loop(make_client(api), settings, [Step()], assemble, once=True, sleep=no_sleep)
    assert len(api.paths("/claim")) == 1 and len(api.paths("/result")) == 1


def test_once_sin_trabajo_sale_sin_dormir(make_client, settings):
    api = FakeApi()
    run_loop(make_client(api), settings, [Step()], assemble, once=True, sleep=no_sleep)
    assert not api.paths("/result")


def test_heartbeat_con_error_de_red_manda_fail_reintentable(make_client, job, tmp_path):
    api = FakeApi()
    client = make_client(api)

    def broken_heartbeat(job_id, step):
        raise ApiError("sin red")

    client.heartbeat = broken_heartbeat
    assert not process_job(client, job, [Step()], assemble, tmp_path, 60)
    ((_, body, _),) = api.paths("/fail")
    assert body["retryable"] is True
    assert not api.paths("/result")
