from pathlib import Path

import pytest

from guitarra_worker.adapters.transcriber import TranscriberUnavailable
from guitarra_worker.api_client import Job
from guitarra_worker.domain.quantize import BeatGrid, TimedNote
from guitarra_worker.domain.riff_candidates import MIN_NOTES, SectionSpan
from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.riffs import ChartInfo, RiffsStep, transcribe_section_riffs

GRID = BeatGrid(beats_s=[i * 0.5 for i in range(80)], bpm=120.0)


class FakeTranscriber:
    def __init__(self, notes):
        self.notes = notes

    def transcribe(self, wav_path: Path):
        return self.notes


class MissingTranscriber:
    def transcribe(self, wav_path: Path):
        raise TranscriberUnavailable("falta basic-pitch")


def test_returns_events_per_candidate_section():
    notes = [TimedNote(1 + i * 0.25, 1.2 + i * 0.25, 60 + i % 5, 0.8) for i in range(MIN_NOTES)]
    sections = [SectionSpan("verso-1", "Verso", 0.0, 8.0), SectionSpan("coro-2", "Coro", 8.0, 16.0)]
    riffs = transcribe_section_riffs(FakeTranscriber(notes), Path("g.wav"), sections, GRID)
    assert list(riffs) == ["verso-1"]
    assert all(set(e) == {"midi", "t", "dur", "confidence"} for e in riffs["verso-1"])
    assert riffs["verso-1"][0]["t"] == pytest.approx(2.0)


def test_unavailable_transcriber_propagates_for_the_step_to_skip():
    with pytest.raises(TranscriberUnavailable):
        transcribe_section_riffs(MissingTranscriber(), Path("g.wav"), [], GRID)


def _ctx(tmp_path, with_stem=True):
    stem = tmp_path / "guitar.wav"
    stem.write_bytes(b"x")
    outputs = {"separate": {"stems": {"guitar": str(stem)}}} if with_stem else {}
    messages: list[str] = []
    job = Job(job_id=1, song_id=1, job_type="separation")
    return PipelineContext(job, tmp_path, outputs, messages.append), messages


def test_step_skips_without_basic_pitch(tmp_path):
    ctx, messages = _ctx(tmp_path)
    result = RiffsStep(MissingTranscriber(), lambda _: ChartInfo([], GRID)).run(ctx)
    assert result["riffs"] == {} and "basic-pitch" in result["skipped"]
    assert any("salteados" in m for m in messages)


def test_step_without_chart_is_skipped_not_failed(tmp_path):
    ctx, _ = _ctx(tmp_path)
    assert RiffsStep(FakeTranscriber([]), lambda _: None).run(ctx)["riffs"] == {}


def test_step_without_guitar_stem_is_skipped(tmp_path):
    ctx, _ = _ctx(tmp_path, with_stem=False)
    result = RiffsStep(FakeTranscriber([]), lambda _: ChartInfo([], GRID)).run(ctx)
    assert result["riffs"] == {} and "guitarra" in result["skipped"]
