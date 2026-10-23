import json
from pathlib import Path

import httpx

from guitarra_worker.api_client import Job
from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.strum import StrumStep
from guitarra_worker.strum.ollama_chooser import OllamaChooser

NO_DATA = {"strum": None, "arpeggio": None}


def make_ctx(tmp_path: Path, tempo: dict | None) -> PipelineContext:
    job = Job(
        job_id=1,
        song_id=1,
        title="T",
        artist="A",
        source="youtube",
        url="u",
        youtube_id="abc",
        spotify_id=None,
        attempt=1,
    )
    outputs = {} if tempo is None else {"tempo": tempo}
    return PipelineContext(job=job, song_dir=tmp_path, outputs=outputs)


def down_chooser() -> OllamaChooser:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("rechazada")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaChooser("http://x", "m", 1.0, client=client)


def test_step_returns_strum_and_arpeggio_for_the_bar(tmp_path):
    ctx = make_ctx(tmp_path, {"bpm": 100.0, "beats_per_bar": 3})
    out = StrumStep(down_chooser()).run(ctx)
    assert out["strum"]["source"] == "rules"
    assert out["strum"]["beats_per_cycle"] == 3
    assert out["arpeggio"]["pattern_id"]
    json.dumps(out)


def test_step_without_tempo_is_no_data(tmp_path):
    assert StrumStep(None).run(make_ctx(tmp_path, None)) == NO_DATA


def test_step_with_unsupported_bar_is_no_data(tmp_path):
    ctx = make_ctx(tmp_path, {"bpm": 100.0, "beats_per_bar": 7})
    assert StrumStep(None).run(ctx) == NO_DATA


def test_step_with_missing_bpm_is_no_data(tmp_path):
    ctx = make_ctx(tmp_path, {"bpm": None, "beats_per_bar": 4})
    assert StrumStep(None).run(ctx) == NO_DATA
