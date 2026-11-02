import importlib.util
import sys

import numpy as np
import pytest
from scipy.io import wavfile

from guitarra_worker.adapters.transcriber import BasicPitchTranscriber, TranscriberUnavailable
from guitarra_worker.domain.quantize import BeatGrid, quantize_section

SR = 22_050
HAS_BASIC_PITCH = importlib.util.find_spec("basic_pitch") is not None


def pluck(midi, seconds):
    t = np.arange(int(seconds * SR)) / SR
    f0 = 440.0 * 2 ** ((midi - 69) / 12)
    wave = sum(np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * (2 + 2 * k)) / k for k in range(1, 7))
    return wave * np.minimum(t / 0.004, 1.0)


def write_riff(path, pitches, step=0.5):
    audio = np.zeros(int((len(pitches) * step + 1.0) * SR))
    for i, midi in enumerate(pitches):
        wave = pluck(midi, step + 0.3)
        start = int(i * step * SR)
        audio[start : start + len(wave)] += wave
    audio = 0.8 * audio / np.max(np.abs(audio))
    wavfile.write(path, SR, audio.astype(np.float32))


def test_missing_basic_pitch_raises_unavailable(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "basic_pitch", None)
    monkeypatch.setitem(sys.modules, "basic_pitch.inference", None)
    with pytest.raises(TranscriberUnavailable):
        BasicPitchTranscriber().transcribe(tmp_path / "x.wav")


@pytest.mark.skipif(not HAS_BASIC_PITCH, reason="basic-pitch no está instalado")
def test_real_basic_pitch_finds_synthetic_riff(tmp_path):
    pitches = [57, 60, 62, 64, 62, 60]
    wav = tmp_path / "riff.wav"
    write_riff(wav, pitches)
    notes = BasicPitchTranscriber().transcribe(wav)
    assert [n.midi for n in notes] == pitches
    assert all(0.0 <= n.confidence <= 1.0 and n.offset_s > n.onset_s for n in notes)
    events = quantize_section(notes, 0.0, 4.0, BeatGrid(beats_s=[], bpm=120.0))
    assert [e.t for e in events] == pytest.approx(list(range(len(pitches))), abs=0.01)
