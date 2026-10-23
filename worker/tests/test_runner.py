import json
import time

import pytest

from guitarra_worker.api_client import ApiError, LeaseLostError
from guitarra_worker.pipeline.runner import (
    Heartbeat,
    read_step_cache,
    run_pipeline,
    write_step_cache,
)


class FakeStep:
    def __init__(self, name, version="1", fail=None):
        self.name, self.version, self.fail, self.runs = name, version, fail, 0

    def run(self, ctx):
        self.runs += 1
        if self.fail:
            raise self.fail
        return {"from": self.name, "seen": sorted(ctx.outputs)}


def run(steps, job, tmp_path, send=lambda step: None):
    with Heartbeat(send, 60) as hb:
        return run_pipeline(steps, job, tmp_path, hb, lambda outputs: outputs[steps[-1].name])


def test_segunda_corrida_reusa_cache(job, tmp_path):
    a, b = FakeStep("a"), FakeStep("b")
    run([a, b], job, tmp_path)
    run([a, b], job, tmp_path)
    assert (a.runs, b.runs) == (1, 1)
    assert (tmp_path / "abc123" / "steps" / "a.json").exists()


def test_version_distinta_reejecuta_solo_ese_paso(job, tmp_path):
    a, b = FakeStep("a"), FakeStep("b")
    run([a, b], job, tmp_path)
    b2 = FakeStep("b", version="2")
    run([a, b2], job, tmp_path)
    assert (a.runs, b2.runs) == (1, 1)


def test_paso_fallido_no_deja_cache_y_se_reintenta(job, tmp_path):
    a, b = FakeStep("a"), FakeStep("b", fail=ValueError("x"))
    with pytest.raises(ValueError):
        run([a, b], job, tmp_path)
    b_ok = FakeStep("b")
    out = run([a, b_ok], job, tmp_path)
    assert (a.runs, b_ok.runs) == (1, 1)
    assert out["seen"] == ["a"]


def test_cache_corrupta_se_reejecuta(job, tmp_path):
    a = FakeStep("a")
    run([a], job, tmp_path)
    (tmp_path / "abc123" / "steps" / "a.json").write_text("{roto", encoding="utf-8")
    run([a], job, tmp_path)
    assert a.runs == 2


def test_clave_por_song_id_sin_youtube_id(job, tmp_path):
    job.youtube_id = None
    run([FakeStep("a")], job, tmp_path)
    assert (tmp_path / "song-3" / "steps" / "a.json").exists()


def test_escritura_atomica_sin_temporales(tmp_path):
    path = tmp_path / "s" / "x.json"
    write_step_cache(path, "1", {"k": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": "1", "output": {"k": 1}}
    assert [p.name for p in path.parent.iterdir()] == ["x.json"]
    assert read_step_cache(path, "1") == {"k": 1}
    assert read_step_cache(path, "2") is None


def test_heartbeat_con_current_step(job, tmp_path):
    sent = []
    run([FakeStep("a"), FakeStep("b")], job, tmp_path, send=sent.append)
    assert sent[:2] == ["a", "b"]


def test_heartbeat_409_aborta_antes_de_correr_el_paso(job, tmp_path):
    a = FakeStep("a")

    def send(step):
        raise LeaseLostError()

    with pytest.raises(LeaseLostError):
        run([a], job, tmp_path, send=send)
    assert a.runs == 0


def test_cambiar_version_de_un_paso_reejecuta_los_siguientes(job, tmp_path):
    a, b, c = FakeStep("a"), FakeStep("b"), FakeStep("c")
    run([a, b, c], job, tmp_path)
    a2 = FakeStep("a", version="2")
    run([a2, b, c], job, tmp_path)
    assert (a2.runs, b.runs, c.runs) == (1, 2, 2)


def test_cambiar_version_del_ultimo_no_toca_los_anteriores(job, tmp_path):
    a, b = FakeStep("a"), FakeStep("b")
    run([a, b], job, tmp_path)
    b2 = FakeStep("b", version="2")
    run([a, b2], job, tmp_path)
    assert (a.runs, b2.runs) == (1, 1)


def test_assemble_arma_el_resultado(job, tmp_path):
    with Heartbeat(lambda step: None, 60) as hb:
        result = run_pipeline([FakeStep("a")], job, tmp_path, hb, lambda o: {"x": o["a"]["from"]})
    assert result == {"x": "a"}


def test_hilo_de_heartbeat_sobrevive_a_errores_de_api():
    calls = []

    def send(step):
        calls.append(step)
        raise ApiError("sin red")

    with Heartbeat(send, 0.01) as hb:
        deadline = time.monotonic() + 2
        while len(calls) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        hb.check()
    assert len(calls) >= 3


def test_beat_propaga_error_de_api():
    def send(step):
        raise ApiError("sin red")

    with Heartbeat(send, 60) as hb, pytest.raises(ApiError):
        hb.beat("a")


class TokenStep(FakeStep):
    """Paso cuya salida depende de un dato del trabajo (como el texto de Cifra Club)."""

    def cache_token(self, job):
        return job.cifra_text or ""


def test_token_de_cache_distinto_reejecuta_ese_paso_y_los_siguientes(job, tmp_path):
    a, token, after = FakeStep("a"), TokenStep("t"), FakeStep("z")
    run([a, token, after], job.model_copy(update={"cifra_text": "uno"}), tmp_path)
    run([a, token, after], job.model_copy(update={"cifra_text": "uno"}), tmp_path)
    assert (a.runs, token.runs, after.runs) == (1, 1, 1)
    run([a, token, after], job.model_copy(update={"cifra_text": "dos"}), tmp_path)
    assert (a.runs, token.runs, after.runs) == (1, 2, 2)
