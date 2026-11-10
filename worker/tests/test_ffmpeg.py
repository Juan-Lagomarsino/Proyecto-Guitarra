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


def test_convert_to_m4a_arma_el_comando(tmp_path):
    from guitarra_worker.adapters.ffmpeg import convert_to_m4a

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        (tmp_path / "o.m4a.part").write_bytes(b"aac")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    source = make_wav(tmp_path / "in.wav")
    convert_to_m4a("ff", source, tmp_path / "o.m4a", run=fake_run)
    cmd = calls[0]
    assert cmd[0] == "ff" and str(source) in cmd
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert cmd[cmd.index("-b:a") + 1] == "160k"
    assert cmd[cmd.index("-ac") + 1] == "2"
    assert cmd[cmd.index("-f") + 1] == "ipod" and cmd[-1] == str(tmp_path / "o.m4a.part")
    assert (tmp_path / "o.m4a").read_bytes() == b"aac"
    assert not (tmp_path / "o.m4a.part").exists()


def test_convert_to_m4a_error_de_ffmpeg_falla_claro(tmp_path):
    from guitarra_worker.adapters.ffmpeg import convert_to_m4a

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "boom")

    with pytest.raises(RetryableStepError, match="boom"):
        convert_to_m4a("ff", make_wav(tmp_path / "in.wav"), tmp_path / "o.m4a", run=fake_run)
    assert not (tmp_path / "o.m4a").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_convert_to_m4a_real(tmp_path):
    from guitarra_worker.adapters.ffmpeg import convert_to_m4a

    source = make_wav(tmp_path / "in.wav", seconds=1.0, rate=48_000, channels=2)
    dest = tmp_path / "out" / "original.m4a"
    convert_to_m4a(shutil.which("ffmpeg"), source, dest)
    assert dest.stat().st_size > 0
    probe = subprocess.run(
        [shutil.which("ffmpeg"), "-hide_banner", "-i", str(dest), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0
    assert "aac" in probe.stderr and "mov,mp4,m4a" in probe.stderr
