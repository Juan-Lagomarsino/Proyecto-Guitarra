from pathlib import Path

import numpy as np

from guitarra_worker.api_client import Job
from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.structure import StructureStep
from test_structure_domain import build_song


class FakeSimilarity:
    def __init__(self, ssm: np.ndarray) -> None:
        self.ssm = ssm
        self.calls: list[tuple[Path, int]] = []

    def self_similarity(self, wav_path: Path, beats: np.ndarray) -> np.ndarray:
        self.calls.append((wav_path, len(beats)))
        return self.ssm


def make_ctx(tmp_path: Path, outputs: dict) -> PipelineContext:
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
    return PipelineContext(job=job, song_dir=tmp_path, outputs=outputs)


def outputs_for(layout: str):
    ssm, beats, downbeats, duration = build_song(layout)
    outputs = {
        "download": {"wav_path": "x/original.wav", "duration_s": duration},
        "tempo": {"beats": beats.tolist(), "downbeats": downbeats.tolist()},
    }
    return ssm, outputs


def test_devuelve_secciones_serializables(tmp_path):
    ssm, outputs = outputs_for("ABABCB")
    similarity = FakeSimilarity(ssm)
    result = StructureStep(similarity).run(make_ctx(tmp_path, outputs))
    assert [s["name"] for s in result["sections"]] == [
        "estrofa",
        "estribillo",
        "estrofa",
        "estribillo",
        "puente",
        "estribillo",
    ]
    assert result["sections"][1] == {
        "order": 1,
        "start_s": 16.0,
        "end_s": 32.0,
        "start_bar": 8,
        "end_bar": 16,
        "group": "B",
        "name": "estribillo",
    }
    assert result["confidence"] == "media"
    assert similarity.calls == [(Path("x/original.wav"), 192)]


def test_sin_salida_de_tempo_es_sin_datos(tmp_path):
    _, outputs = outputs_for("ABAB")
    del outputs["tempo"]
    similarity = FakeSimilarity(np.zeros((0, 0)))
    result = StructureStep(similarity).run(make_ctx(tmp_path, outputs))
    assert result == {"sections": [], "confidence": "baja"}
    assert similarity.calls == []


def test_sin_salida_de_tempo_deja_un_aviso(tmp_path, caplog):
    _, outputs = outputs_for("ABAB")
    del outputs["tempo"]
    with caplog.at_level("WARNING"):
        StructureStep(FakeSimilarity(np.zeros((0, 0)))).run(make_ctx(tmp_path, outputs))
    assert "tempo" in caplog.text


def test_tempo_sin_downbeats_es_sin_datos(tmp_path):
    _, outputs = outputs_for("ABAB")
    outputs["tempo"]["downbeats"] = []
    result = StructureStep(FakeSimilarity(np.zeros((0, 0)))).run(make_ctx(tmp_path, outputs))
    assert result["sections"] == []
