from pathlib import Path

import pytest

from guitarra_worker.domain.chords import RawChord
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext
from guitarra_worker.steps.chords import ChordsStep
from guitarra_worker.steps.key import KeyStep

BEATS = [i * 0.5 for i in range(9)]  # 0.0 .. 4.0


class FakeRecognizer:
    name = "fake"

    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def recognize(self, wav_path):
        self.calls.append(wav_path)
        return self.raw


def ctx_for(job, tmp_path, outputs):
    return PipelineContext(job=job, song_dir=tmp_path, outputs=outputs)


def outputs(beats=BEATS):
    return {
        "download": {"wav_path": "C:/audio/original.wav", "duration_s": 4.5},
        "tempo": {"beats": beats},
    }


def test_chords_usa_el_wav_de_download_y_la_grilla_de_tempo(job, tmp_path):
    recognizer = FakeRecognizer([RawChord(0.0, 2.0, "C"), RawChord(2.0, 5.0, "A:min")])
    out = ChordsStep(recognizer).run(ctx_for(job, tmp_path, outputs()))
    assert recognizer.calls == [Path("C:/audio/original.wav")]
    assert out["model"] == "fake"
    assert out["chords"] == [
        {"start": 0.0, "end": 2.0, "label": "C", "confidence": 1.0},
        {"start": 2.0, "end": 4.5, "label": "Am", "confidence": 1.0},
    ]


def test_chords_sin_beats_devuelve_lista_vacia_sin_llamar_al_modelo(job, tmp_path):
    recognizer = FakeRecognizer([RawChord(0.0, 2.0, "C")])
    out = ChordsStep(recognizer).run(ctx_for(job, tmp_path, outputs(beats=[])))
    assert out["chords"] == []
    assert recognizer.calls == []


def test_chords_sin_paso_de_tempo_avisa_y_devuelve_sin_datos(job, tmp_path, caplog):
    ctx = ctx_for(job, tmp_path, {"download": outputs()["download"]})
    recognizer = FakeRecognizer([RawChord(0.0, 2.0, "C")])
    assert ChordsStep(recognizer).run(ctx)["chords"] == []
    assert "tempo" in caplog.text
    assert recognizer.calls == []


def test_chords_redondea_a_milisegundos(job, tmp_path):
    recognizer = FakeRecognizer([RawChord(0.0, 5.0, "G")])
    out = ChordsStep(recognizer).run(ctx_for(job, tmp_path, outputs(beats=[0.1234567, 0.7654321])))
    assert out["chords"][0]["start"] == 0.123


def test_key_a_partir_de_los_acordes(job, tmp_path):
    chords = [
        {"start": 0.0, "end": 4.0, "label": "G", "confidence": 1.0},
        {"start": 4.0, "end": 6.0, "label": "C", "confidence": 1.0},
        {"start": 6.0, "end": 8.0, "label": "D", "confidence": 1.0},
        {"start": 8.0, "end": 12.0, "label": "G", "confidence": 1.0},
    ]
    out = KeyStep().run(ctx_for(job, tmp_path, {"chords": {"chords": chords}}))
    assert out["key"]["name"] == "G"
    assert out["key"]["mode"] == "major"
    assert out["key"]["relative"] == "Em"
    assert 0 < out["key"]["confidence"] <= 0.6


def test_key_sin_acordes_es_sin_datos(job, tmp_path):
    out = KeyStep().run(ctx_for(job, tmp_path, {"chords": {"chords": []}}))
    assert out == {"key": None}


def test_key_sin_paso_de_acordes_es_error_permanente(job, tmp_path):
    with pytest.raises(PermanentStepError, match="chords"):
        KeyStep().run(ctx_for(job, tmp_path, {}))
