import shutil
import subprocess

import pytest

from guitarra_worker.adapters.ffmpeg import convert_to_wav, find_ffmpeg, read_wav_info
from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError
from wavs import make_wav


def test_find_ffmpeg_prefiere_lo_configurado():
    assert find_ffmpeg("C:/x/ffmpeg.exe") == "C:/x/ffmpeg.exe"


def test_find_ffmpeg_sin_nada_falla_claro(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(PermanentStepError, match="GUITAR_FFMPEG"):
        find_ffmpeg(None)


def test_read_wav_info(tmp_path):
    info = read_wav_info(make_wav(tmp_path / "a.wav", seconds=0.5, rate=48_000, channels=2))
    assert (info.sample_rate, info.channels) == (48_000, 2)
    assert info.duration_s == pytest.approx(0.5, abs=0.01)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_convert_to_wav_real(tmp_path):
    source = make_wav(tmp_path / "in.wav", seconds=1.0, rate=44_100, channels=1)
    dest = tmp_path / "out" / "original.wav"
    convert_to_wav(shutil.which("ffmpeg"), source, dest)
    info = read_wav_info(dest)
    assert (info.sample_rate, info.channels) == (48_000, 2)
    assert info.duration_s == pytest.approx(1.0, abs=0.05)
    assert not dest.with_name("original.wav.part").exists()


def test_convert_to_wav_con_ffmpeg_inexistente(tmp_path):
    source = make_wav(tmp_path / "in.wav")
    with pytest.raises(PermanentStepError):
        convert_to_wav(str(tmp_path / "no-existe.exe"), source, tmp_path / "o.wav")
    assert not (tmp_path / "o.wav").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_entrada_vacia_es_reintentable(tmp_path):
    empty = tmp_path / "vacio.webm"
    empty.write_bytes(b"")
    with pytest.raises(RetryableStepError):
        convert_to_wav(shutil.which("ffmpeg"), empty, tmp_path / "o.wav")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_entrada_basura_es_reintentable(tmp_path):
    junk = tmp_path / "roto.webm"
    junk.write_bytes(b"\x1a\x45\xdf\xa3" + b"\x00" * 20)
    with pytest.raises(RetryableStepError):
        convert_to_wav(shutil.which("ffmpeg"), junk, tmp_path / "o.wav")


def test_formato_no_soportado_es_permanente(tmp_path, monkeypatch):
    fake = subprocess.CompletedProcess([], 1, "", "Decoder not found: Unsupported codec")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    source = make_wav(tmp_path / "in.wav")
    with pytest.raises(PermanentStepError):
        convert_to_wav("ffmpeg", source, tmp_path / "o.wav")
