"""Paso de tempo: con un tracker falso (siempre) y con beat_this real (si están los pesos).

El modelo real no corre en la CI: los pesos pesan ~80 MB y viven fuera del repo. El test real
(clicks a BPM conocido, +-1) corre solo en local con el extra `analysis`; en la CI se omite
si falta `beat_this` o el checkpoint (`scripts/install.ps1` los deja en
`<GuitarApp>/models/beat_this-final0.ckpt`, o donde diga GUITAR_BEAT_THIS_CHECKPOINT).
"""

import importlib.util

import pytest

from guitarra_worker.adapters.beat_this import BeatGrid, BeatThisTracker
from guitarra_worker.config import Settings
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext
from guitarra_worker.steps.tempo import BEATS_KEY, BPM_KEY, DOWNBEATS_KEY, TempoStep
from wavs import make_click_wav, make_wav


class FakeTracker:
    def __init__(self, grid: BeatGrid):
        self.grid = grid
        self.calls = []

    def track(self, wav_path):
        self.calls.append(wav_path)
        return self.grid


def ctx_with_wav(job, wav_path):
    return PipelineContext(
        job=job, song_dir=wav_path.parent, outputs={"download": {"wav_path": str(wav_path)}}
    )


def test_paso_arma_el_resultado_con_la_grilla_del_tracker(job, tmp_path):
    wav = make_wav(tmp_path / "original.wav", seconds=1.0)
    beats = tuple(1.0 + i * 0.5 for i in range(16))  # 120 BPM
    tracker = FakeTracker(BeatGrid(beats, beats[::4]))
    out = TempoStep(tracker).run(ctx_with_wav(job, wav))
    assert tracker.calls == [wav]
    assert out["bpm"] == pytest.approx(120, abs=0.01)
    assert out["beats_per_bar"] == 4
    assert out["first_downbeat_s"] == 1.0
    assert out["downbeats"] == list(beats[::4])


def test_paso_sin_beats_devuelve_vacio_sin_error(job, tmp_path):
    wav = make_wav(tmp_path / "original.wav", seconds=1.0)
    out = TempoStep(FakeTracker(BeatGrid((), ()))).run(ctx_with_wav(job, wav))
    assert out["bpm"] is None
    assert out["beats"] == []


def test_paso_falla_claro_si_no_hay_audio(job, tmp_path):
    ctx = ctx_with_wav(job, tmp_path / "no-esta.wav")
    with pytest.raises(PermanentStepError, match="no-esta.wav"):
        TempoStep(FakeTracker(BeatGrid((), ()))).run(ctx)


SHA = Settings(_env_file=None).beat_this_sha256


def test_tracker_sin_pesos_pide_instalar(tmp_path):
    tracker = BeatThisTracker(tmp_path / "no-hay.ckpt", SHA)
    with pytest.raises(PermanentStepError, match="install.ps1"):
        tracker.track(tmp_path / "x.wav")


def test_tracker_con_pesos_corruptos_no_los_acepta(tmp_path):
    corrupt = tmp_path / "final0.ckpt"
    corrupt.write_bytes(b"truncado")
    with pytest.raises(PermanentStepError, match="corruptos"):
        BeatThisTracker(corrupt, SHA).track(tmp_path / "x.wav")


def _real_checkpoint():
    path = Settings(_env_file=None).beat_this_checkpoint_path
    has_lib = importlib.util.find_spec("beat_this") is not None
    return path if has_lib and path.exists() else None


@pytest.mark.skipif(_real_checkpoint() is None, reason="faltan beat_this o sus pesos")
@pytest.mark.parametrize("bpm", [90, 120, 140])
# Los compases no se afirman acá: sobre clicks sin armonía el modelo reparte los downbeats al
# azar. Se validan con canciones reales (ver el spike, ADR 0006).
def test_beat_this_real_con_clicks_a_bpm_conocido(job, tmp_path, bpm):
    wav = make_click_wav(tmp_path / "original.wav", bpm=bpm, seconds=30)
    out = TempoStep(BeatThisTracker(_real_checkpoint(), SHA)).run(ctx_with_wav(job, wav))
    assert out["bpm"] == pytest.approx(bpm, abs=1)
    assert out["downbeats"], "tiene que haber al menos un downbeat"
    assert set(out["downbeats"]) <= set(out["beats"])
    assert out["beats"] == sorted(out["beats"])


def test_contrato_de_salida_para_acordes_y_estructura(job, tmp_path):
    wav = make_wav(tmp_path / "original.wav", seconds=1.0)
    beats = tuple(0.5 * i for i in range(8))
    out = TempoStep(FakeTracker(BeatGrid(beats, beats[::4]))).run(ctx_with_wav(job, wav))
    assert (BPM_KEY, BEATS_KEY, DOWNBEATS_KEY) == ("bpm", "beats", "downbeats")
    assert isinstance(out[BPM_KEY], float)
    assert set(out[DOWNBEATS_KEY]) <= set(out[BEATS_KEY])
