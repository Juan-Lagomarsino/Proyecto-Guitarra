"""Adaptador de BTC. El test con el modelo real se omite si no están torch y el clon de BTC.

Para correrlo: `pip install -e worker[analisis]`, `scripts/install.ps1` (clona BTC en la caché) o
`GUITAR_BTC_DIR` apuntando al clon.
"""

import os
from pathlib import Path

import pytest

from guitarra_worker.adapters.btc import BtcChordRecognizer, _runs, is_installed
from guitarra_worker.config import Settings
from guitarra_worker.domain.chords import RawChord, snap_to_beats
from guitarra_worker.pipeline.step import PermanentStepError

SAMPLE_RATE = 22_050
CHORD_SECONDS = 3.0
# Acordes de la progresión sintética y sus notas (Hz, octavas 3 y 4).
PROGRESSION = [
    ("C", (130.81, 164.81, 196.00, 261.63, 329.63, 392.00)),
    ("Am", (110.00, 130.81, 164.81, 220.00, 261.63, 329.63)),
    ("F", (87.31, 130.81, 174.61, 220.00, 261.63, 349.23)),
    ("G", (98.00, 123.47, 146.83, 196.00, 246.94, 293.66)),
]


def btc_dir() -> Path:
    return (
        Path(os.environ["GUITAR_BTC_DIR"])
        if "GUITAR_BTC_DIR" in os.environ
        else Settings().btc_path
    )


def test_runs_agrupa_ids_consecutivos_en_tramos_con_tiempos():
    labels = {0: "C", 1: "G", 2: "N"}
    assert _runs([0, 0, 1, 1, 1, 2], 0.5, labels) == [
        RawChord(0.0, 1.0, "C"),
        RawChord(1.0, 2.5, "G"),
        RawChord(2.5, 3.0, "N"),
    ]


def test_runs_sin_ids_no_hay_tramos():
    assert _runs([], 0.5, {}) == []


def test_sin_btc_instalado_el_error_dice_como_arreglarlo(tmp_path):
    assert not is_installed(tmp_path)
    with pytest.raises(PermanentStepError, match="install.ps1"):
        BtcChordRecognizer(tmp_path).recognize(tmp_path / "x.wav")


def test_la_carpeta_de_btc_sale_de_la_config(tmp_path, monkeypatch):
    monkeypatch.delenv("GUITAR_BTC_DIR", raising=False)
    assert Settings(_env_file=None, cache_dir=tmp_path).btc_path == tmp_path / "btc"
    other = tmp_path / "otro"
    assert Settings(_env_file=None, cache_dir=tmp_path, btc_dir=other).btc_path == other


def write_progression(path: Path) -> Path:
    import wave

    import numpy as np

    t = np.arange(int(CHORD_SECONDS * SAMPLE_RATE)) / SAMPLE_RATE
    envelope = np.exp(-t / 2.5)[:, None]
    parts = []
    for _, notes in PROGRESSION:
        tones = sum(sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 2, 3)) for f in notes) / len(
            notes
        )
        parts.append(tones * envelope[:, 0])
    audio = np.concatenate(parts)
    audio = (audio / np.abs(audio).max() * 0.8 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())
    return path


@pytest.mark.skipif(not is_installed(btc_dir()), reason="BTC no está instalado (ver docstring)")
def test_btc_real_reconoce_una_progresion_sintetica(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("librosa")
    wav = write_progression(tmp_path / "progresion.wav")
    raw = BtcChordRecognizer(btc_dir()).recognize(wav)
    beats = [i * 0.5 for i in range(int(CHORD_SECONDS * len(PROGRESSION) / 0.5))]
    spans = snap_to_beats(raw, beats, CHORD_SECONDS * len(PROGRESSION))
    middle = {}
    for index, (name, _) in enumerate(PROGRESSION):
        t = index * CHORD_SECONDS + CHORD_SECONDS / 2
        middle[name] = next(s.label for s in spans if s.start <= t < s.end)
    assert middle == {name: name for name, _ in PROGRESSION}
