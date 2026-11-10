import pytest

from guitarra_worker.api_client import ApiError, LeaseLostError
from guitarra_worker.pipeline.registry import default_steps
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext, RetryableStepError
from guitarra_worker.steps.publish_audio import M4A_NAME, UPLOAD_MARKER_NAME, PublishAudioStep
from wavs import make_wav


class FakeConverter:
    def __init__(self):
        self.calls = []

    def __call__(self, source, dest):
        self.calls.append((source, dest))
        dest.write_bytes(b"m4a-" + source.read_bytes()[:8])


class FakeUploader:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def upload_asset(self, job_id, kind, path):
        if self.error:
            raise self.error
        self.calls.append((job_id, kind, path.read_bytes()))


@pytest.fixture
def ctx(job, tmp_path):
    wav = make_wav(tmp_path / "song" / "original.wav", seconds=0.1, rate=48_000, channels=2)
    return PipelineContext(
        job=job, song_dir=tmp_path / "song", outputs={"download": {"wav_path": str(wav)}}
    )


def test_convierte_y_sube_como_original(ctx):
    conv, up = FakeConverter(), FakeUploader()
    out = PublishAudioStep(conv, up).run(ctx)
    assert len(conv.calls) == 1 and conv.calls[0][1] == ctx.song_dir / M4A_NAME
    assert up.calls[0][:2] == (7, "original")
    assert out["uploaded"] is True and out["kind"] == "original"
    assert (ctx.song_dir / UPLOAD_MARKER_NAME).exists()


def test_no_reconvierte_ni_resube_si_nada_cambio(ctx):
    conv, up = FakeConverter(), FakeUploader()
    step = PublishAudioStep(conv, up)
    step.run(ctx)
    out = step.run(ctx)
    assert len(conv.calls) == 1 and len(up.calls) == 1
    assert out["uploaded"] is False


def test_resube_si_el_m4a_cambio(ctx):
    conv, up = FakeConverter(), FakeUploader()
    step = PublishAudioStep(conv, up)
    step.run(ctx)
    (ctx.song_dir / M4A_NAME).write_bytes(b"otro contenido distinto")
    step.run(ctx)
    assert len(up.calls) == 2


def test_resube_si_cambia_la_cancion(ctx, job):
    conv, up = FakeConverter(), FakeUploader()
    step = PublishAudioStep(conv, up)
    step.run(ctx)
    ctx.job = job.model_copy(update={"song_id": 99})
    step.run(ctx)
    assert len(up.calls) == 2


def test_fallo_de_red_es_reintentable_con_mensaje_claro(ctx):
    step = PublishAudioStep(FakeConverter(), FakeUploader(ApiError("caído")))
    with pytest.raises(RetryableStepError, match="No pude subir el audio"):
        step.run(ctx)
    assert not (ctx.song_dir / UPLOAD_MARKER_NAME).exists()


def test_rechazo_4xx_es_permanente(ctx):
    err = ApiError("rechazado", status_code=413)
    with pytest.raises(PermanentStepError, match="413"):
        PublishAudioStep(FakeConverter(), FakeUploader(err)).run(ctx)


def test_lease_perdido_sube_tal_cual(ctx):
    with pytest.raises(LeaseLostError):
        PublishAudioStep(FakeConverter(), FakeUploader(LeaseLostError("x"))).run(ctx)


def test_registro_inserta_el_paso_despues_de_download():
    from guitarra_worker.config import Settings

    steps = default_steps(Settings(_env_file=None), uploader=FakeUploader())
    assert [s.name for s in steps][:3] == ["source", "download", "publish_audio"]


def test_cache_del_runner_se_invalida_si_cambia_la_cancion(job, tmp_path):
    from guitarra_worker.pipeline.runner import Heartbeat, run_pipeline

    class FakeDownload:
        name = "download"
        version = "1"

        def run(self, ctx):
            wav = make_wav(ctx.song_dir / "original.wav", seconds=0.1, rate=48_000, channels=2)
            return {"wav_path": str(wav)}

    up = FakeUploader()
    steps = [FakeDownload(), PublishAudioStep(FakeConverter(), up)]
    with Heartbeat(lambda step: None, 60) as hb:
        run_pipeline(steps, job, tmp_path, hb, lambda o: {})
        run_pipeline(steps, job.model_copy(update={"song_id": 99}), tmp_path, hb, lambda o: {})
    assert len(up.calls) == 2
