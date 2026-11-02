import json

import httpx
import numpy as np
import pytest

from conftest import JOB
from guitarra_worker.adapters.demucs import (
    INSTALL_HINT,
    DemucsSeparator,
    ensure_weights,
    read_wav_float,
    write_wav_float,
)
from guitarra_worker.api_client import ApiClient, Job
from guitarra_worker.config import Settings
from guitarra_worker.domain.mixing import PEAK_LIMIT, STEM_NAMES
from guitarra_worker.loop import run_loop
from guitarra_worker.pipeline.registry import default_steps, separation_steps
from guitarra_worker.pipeline.step import PermanentStepError
from wavs import make_wav

RATE = 8000


class FakeSeparator:
    """Pistas sintéticas: un tono distinto por instrumento."""

    def __init__(self, amp=0.1):
        self.calls = 0
        self.amp = amp

    def separate(self, wav_path, out_dir, progress=None):
        self.calls += 1
        t = np.arange(RATE) / RATE
        stems = {}
        for i, name in enumerate(STEM_NAMES):
            wave = (self.amp * np.sin(2 * np.pi * 100 * (i + 1) * t)).astype(np.float32)
            stems[name] = out_dir / f"{name}.wav"
            write_wav_float(stems[name], RATE, np.stack([wave, wave], axis=1))
        return stems


def fake_m4a(source, dest):
    dest.write_bytes(b"m4a:" + source.read_bytes())


class FakeYoutube:
    def download_wav(self, video_id, dest, progress=None):
        make_wav(dest, seconds=0.1, rate=48_000, channels=2)


class Api:
    """API falsa: guarda subidas (binario) y JSONs."""

    def __init__(self, jobs):
        self.jobs = list(jobs)
        self.uploads, self.results, self.fails = [], [], []

    def handler(self, request):
        path = request.url.path
        if path.endswith("/claim"):
            return httpx.Response(200, json=self.jobs.pop(0)) if self.jobs else httpx.Response(204)
        if "/assets/" in path:
            self.uploads.append((path, request.content))
        elif path.endswith("/result"):
            self.results.append(json.loads(request.content))
        elif path.endswith("/fail"):
            self.fails.append(json.loads(request.content))
        return httpx.Response(200)


def build(tmp_path, separator, jobs, monkeypatch):
    api = Api(jobs)
    client = ApiClient(
        "http://api", "tok", "w1", transport=httpx.MockTransport(api.handler), sleep=lambda s: None
    )
    settings = Settings(_env_file=None, cache_dir=tmp_path / "cache", heartbeat_interval_s=60)
    steps = separation_steps(client, settings, separator)
    # descarga falsa y conversión falsa (sin red ni ffmpeg)
    steps[1]._youtube = FakeYoutube()
    steps[4]._convert = fake_m4a
    return api, client, settings, steps


SEPARATION_JOB = {**JOB, "job_type": "separation"}


def test_separacion_sube_no_guitar_y_manda_result(tmp_path, monkeypatch):
    sep = FakeSeparator()
    api, client, settings, steps = build(tmp_path, sep, [SEPARATION_JOB], monkeypatch)
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    assert [p for p, _ in api.uploads] == ["/api/v1/jobs/7/assets/no_guitar"]
    assert api.uploads[0][1].startswith(b"m4a:")
    assert api.results == [{"worker_id": "w1"}] and not api.fails
    # la mezcla subida es la de todo menos guitarra
    mix_wav = settings.cache_dir / "abc123" / "no_guitar.wav"
    _, mixed = read_wav_float(mix_wav)
    assert np.abs(mixed).max() <= PEAK_LIMIT


def test_segunda_corrida_no_vuelve_a_separar(tmp_path, monkeypatch):
    sep = FakeSeparator()
    api, client, settings, steps = build(
        tmp_path, sep, [SEPARATION_JOB, {**SEPARATION_JOB, "job_id": 8}], monkeypatch
    )
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    assert sep.calls == 1
    assert len(api.results) == 2


def test_mezcla_no_satura_con_pistas_fuertes(tmp_path, monkeypatch):
    api, client, settings, steps = build(
        tmp_path, FakeSeparator(amp=0.9), [SEPARATION_JOB], monkeypatch
    )
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    _, mixed = read_wav_float(settings.cache_dir / "abc123" / "no_guitar.wav")
    assert 0.5 < np.abs(mixed).max() <= PEAK_LIMIT + 1e-6


def test_el_loop_despacha_analisis_por_su_pipeline(tmp_path, monkeypatch):
    sep = FakeSeparator()
    api, client, settings, steps = build(tmp_path, sep, [JOB], monkeypatch)

    class Analyze:
        name, version = "a", "1"

        def run(self, ctx):
            return {"metadata": {"bpm": 1}}

    run_loop(client, settings, [Analyze()], lambda o: o["a"], separation_steps=steps, once=True)
    assert api.results[0]["metadata"] == {"bpm": 1} and sep.calls == 0 and not api.uploads


def test_claim_viejo_sin_job_type_es_analisis():
    assert Job.model_validate(JOB).job_type == "analyze"


def test_worker_sin_pipeline_de_separacion_falla_permanente(tmp_path, monkeypatch):
    api, client, settings, _ = build(tmp_path, FakeSeparator(), [SEPARATION_JOB], monkeypatch)
    run_loop(client, settings, [], lambda o: {}, once=True)
    assert api.fails[0]["retryable"] is False and not api.results


def test_sin_demucs_error_permanente_con_instrucciones(tmp_path, monkeypatch):
    sep = DemucsSeparator(tmp_path / "models")  # sin demucs/torch instalados en la CI
    api, client, settings, steps = build(tmp_path, sep, [SEPARATION_JOB], monkeypatch)
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    (fail,) = api.fails
    assert fail["retryable"] is False and "install.ps1" in fail["error"]
    assert not api.results and not api.uploads


def test_sin_pesos_error_permanente(tmp_path, monkeypatch):
    sep = DemucsSeparator(tmp_path / "models")
    monkeypatch.setattr(sep, "_load_libs", lambda: (None, None, None))
    with pytest.raises(PermanentStepError, match="pesos") as info:
        sep.separate(tmp_path / "x.wav", tmp_path / "out")
    assert INSTALL_HINT in str(info.value)


def test_sin_job_youtube_id_es_permanente(tmp_path, monkeypatch):
    api, client, settings, steps = build(
        tmp_path, FakeSeparator(), [{**SEPARATION_JOB, "youtube_id": None}], monkeypatch
    )
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)
    assert api.fails[0]["retryable"] is False


def test_el_registro_de_analisis_no_cambia():
    names = [s.name for s in default_steps(Settings(_env_file=None))]
    assert "separate" not in names


def test_ensure_weights_reintenta_y_falla_con_mensaje(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    pytest.importorskip("demucs")
    settings = Settings(_env_file=None, demucs_model_dir=tmp_path / "m")
    attempts = []

    def load(name):
        attempts.append(name)
        raise OSError("sin red")

    with pytest.raises(RuntimeError, match="htdemucs_6s"):
        ensure_weights(settings, sleep=lambda s: None, load=load)
    assert len(attempts) == 3


def test_ruta_de_modelos_por_defecto_y_por_env(tmp_path):
    base = Settings(_env_file=None, cache_dir=tmp_path / "cache")
    assert base.demucs_model_path == tmp_path / "models" / "demucs"
    custom = Settings(_env_file=None, demucs_model_dir=tmp_path / "x")
    assert custom.demucs_model_path == tmp_path / "x"


class FakeRunner:
    """Modelo falso: devuelve 6 pistas iguales a mix/6 y registra lo que recibió."""

    samplerate = 8000
    sources = list(STEM_NAMES)

    def __init__(self):
        self.received = None

    def run(self, mix):
        self.received = mix
        return np.stack([mix / 6] * 6)


def test_normalizacion_ida_y_vuelta():
    from guitarra_worker.adapters.demucs import denormalize_sources, normalize_mix

    rng = np.random.default_rng(0)
    mix = (rng.standard_normal((2, 500)) * 0.2 + 0.05).astype(np.float32)
    normalized, norm = normalize_mix(mix)
    ref = normalized.mean(axis=0)
    assert abs(ref.mean()) < 1e-5 and abs(ref.std() - 1) < 1e-4
    assert np.allclose(denormalize_sources(normalized[None], norm)[0], mix, atol=1e-5)


def test_normalizacion_de_silencio_no_da_nan():
    from guitarra_worker.adapters.demucs import normalize_mix

    normalized, norm = normalize_mix(np.zeros((2, 10), dtype=np.float32))
    assert not np.isnan(normalized).any() and norm.std == 1.0


def test_adaptador_normaliza_la_entrada_y_desnormaliza_las_pistas(tmp_path):
    wav = tmp_path / "in.wav"
    t = np.arange(RATE) / RATE
    tone = (0.3 * np.sin(2 * np.pi * 220 * t) + 0.1).astype(np.float32)
    write_wav_float(wav, RATE, np.stack([tone, tone], axis=1))
    runner = FakeRunner()
    stems = DemucsSeparator(tmp_path / "m", runner=runner).separate(wav, tmp_path / "out")
    ref = runner.received.mean(axis=0)
    assert (
        abs(ref.mean()) < 1e-4 and abs(ref.std() - 1) < 1e-3
    )  # el modelo vio la mezcla normalizada
    assert set(stems) == set(STEM_NAMES)
    _, drums = read_wav_float(stems["drums"])
    mean = tone.mean()
    assert np.allclose(drums[:, 0], (tone - mean) / 6 + mean, atol=1e-4)  # vuelve a la escala


def test_wav_de_8_bits_sin_signo_se_rechaza(tmp_path):
    from scipy.io import wavfile

    path = tmp_path / "u8.wav"
    wavfile.write(path, RATE, np.full((10, 2), 128, dtype=np.uint8))
    with pytest.raises(PermanentStepError, match="no soportado"):
        read_wav_float(path)
