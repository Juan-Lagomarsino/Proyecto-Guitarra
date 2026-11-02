"""Riffs en el trabajo de separación (F5-T08): transcriptor falso + MockTransport."""

import httpx

from guitarra_worker.adapters.transcriber import TranscriberUnavailable
from guitarra_worker.api_client import ApiClient
from guitarra_worker.config import Settings
from guitarra_worker.domain.quantize import TimedNote
from guitarra_worker.loop import run_loop
from guitarra_worker.pipeline.registry import separation_steps
from test_separation import SEPARATION_JOB, Api, FakeSeparator, FakeYoutube, fake_m4a


class FakeTranscriber:
    def __init__(self):
        self.calls = 0

    def transcribe(self, wav_path):
        self.calls += 1
        return [TimedNote(i * 0.25, i * 0.25 + 0.2, 45 + (i % 3), 0.8) for i in range(10)]


class MissingTranscriber:
    def transcribe(self, wav_path):
        raise TranscriberUnavailable("falta basic-pitch")


CHART = {
    "bpm": 120.0,
    "time_signature": "4/4",
    "capo": 0,
    "beat_grid": {"beats_s": [i * 0.5 for i in range(40)], "downbeats_s": [0.0, 2.0]},
    "sections": [{"id": "verso-1", "name": "Verso", "start_s": 0.0, "end_s": 8.0}],
}
JOB_WITH_CHART = {**SEPARATION_JOB, "chart": CHART}


def build(tmp_path, jobs, transcriber):
    api = Api(jobs)
    client = ApiClient(
        "http://api", "tok", "w1", transport=httpx.MockTransport(api.handler), sleep=lambda s: None
    )
    settings = Settings(_env_file=None, cache_dir=tmp_path / "cache", heartbeat_interval_s=60)
    steps = separation_steps(client, settings, FakeSeparator(), transcriber)
    steps[1]._youtube = FakeYoutube()
    steps[4]._convert = fake_m4a
    return api, client, settings, steps


def run_once(client, settings, steps):
    run_loop(client, settings, [], lambda o: {}, separation_steps=steps, once=True)


def test_result_de_separacion_incluye_riffs(tmp_path):
    api, client, settings, steps = build(tmp_path, [JOB_WITH_CHART], FakeTranscriber())
    run_once(client, settings, steps)
    assert not api.fails
    riffs = api.results[0]["riffs"]
    assert list(riffs) == ["verso-1"]
    notation = riffs["verso-1"]
    assert notation["bpm"] == 120.0 and notation["time_signature"] == "4/4"
    assert len(notation["events"]) == 10
    assert set(notation["events"][0]) == {"t", "dur", "string", "fret", "technique", "confidence"}


def test_sin_chart_el_result_no_trae_riffs(tmp_path):
    transcriber = FakeTranscriber()
    api, client, settings, steps = build(tmp_path, [SEPARATION_JOB], transcriber)
    run_once(client, settings, steps)
    assert api.results == [{"worker_id": "w1"}] and not api.fails
    assert transcriber.calls == 0


def test_sin_basic_pitch_el_trabajo_termina_sin_riffs(tmp_path):
    api, client, settings, steps = build(tmp_path, [JOB_WITH_CHART], MissingTranscriber())
    run_once(client, settings, steps)
    assert api.results == [{"worker_id": "w1"}] and not api.fails


def test_preferencias_nuevas_no_reusan_riffs_viejos(tmp_path):
    prefs = {"positions": {"45": {"6,5": 1.0}, "46": {"6,6": 1.0}, "47": {"6,7": 1.0}}}
    jobs = [JOB_WITH_CHART, {**JOB_WITH_CHART, "job_id": 8, "fingering_preferences": prefs}]
    transcriber = FakeTranscriber()
    api, client, settings, steps = build(tmp_path, jobs, transcriber)
    run_once(client, settings, steps)
    run_once(client, settings, steps)
    first, second = (r["riffs"]["verso-1"]["events"] for r in api.results)
    assert transcriber.calls == 1  # la transcripción se reusa, el armado no
    assert first != second
    assert any(e["string"] == 6 and e["fret"] == 5 for e in second)
