import hashlib
import importlib.util
import sys

import httpx
import pytest

from guitarra_worker.adapters import beat_this_weights
from guitarra_worker.adapters.beat_this_weights import ensure_checkpoint
from guitarra_worker.config import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("GUITAR_BEAT_THIS_CHECKPOINT", str(tmp_path / "models" / "final0.ckpt"))
    monkeypatch.setenv("GUITAR_BEAT_THIS_SHA256", hashlib.sha256(b"pesos").hexdigest())
    monkeypatch.setenv("GUITAR_BEAT_THIS_URL", "http://oficial/final0.ckpt")
    monkeypatch.setenv("GUITAR_BEAT_THIS_MIRROR_URL", "http://espejo/model.safetensors")
    return Settings(_env_file=None)


class FakeDownloader:
    def __init__(self, failing_urls=(), fail_first=0):
        self.failing_urls = set(failing_urls)
        self.fail_first = fail_first
        self.urls = []

    def __call__(self, url, dest):
        self.urls.append(url)
        if url in self.failing_urls or len(self.urls) <= self.fail_first:
            raise httpx.ConnectError("503")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"pesos")


def no_sleep(seconds):
    return None


def test_ruta_por_defecto_vive_junto_a_la_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("GUITAR_CACHE_DIR", str(tmp_path / "app" / "cache"))
    monkeypatch.delenv("GUITAR_BEAT_THIS_CHECKPOINT", raising=False)
    path = Settings(_env_file=None).beat_this_checkpoint_path
    assert path == tmp_path / "app" / "models" / "beat_this-final0.ckpt"


def test_baja_del_host_oficial(settings):
    download = FakeDownloader()
    path = ensure_checkpoint(settings, download, sleep=no_sleep)
    assert path.read_bytes() == b"pesos"
    assert download.urls == ["http://oficial/final0.ckpt"]


def test_reintenta_antes_de_rendirse(settings):
    download = FakeDownloader(fail_first=2)
    ensure_checkpoint(settings, download, sleep=no_sleep)
    assert download.urls == ["http://oficial/final0.ckpt"] * 3


def test_cae_al_espejo_y_convierte(settings):
    download = FakeDownloader(failing_urls=["http://oficial/final0.ckpt"])
    converted = []

    def convert(source, dest):
        converted.append(source.name)
        dest.write_bytes(b"pesos")

    path = ensure_checkpoint(settings, download, convert, sleep=no_sleep)
    assert path.read_bytes() == b"pesos"
    assert converted == ["final0.safetensors"]
    assert not path.with_suffix(".safetensors").exists()
    assert download.urls[-1] == "http://espejo/model.safetensors"


def test_falla_si_no_anda_ningun_host(settings):
    download = FakeDownloader(
        failing_urls=["http://oficial/final0.ckpt", "http://espejo/model.safetensors"]
    )
    with pytest.raises(RuntimeError, match="espejo"):
        ensure_checkpoint(settings, download, sleep=no_sleep)


def test_es_idempotente(settings):
    settings.beat_this_checkpoint_path.parent.mkdir(parents=True)
    settings.beat_this_checkpoint_path.write_bytes(b"pesos")
    download = FakeDownloader()
    ensure_checkpoint(settings, download, sleep=no_sleep)
    assert download.urls == []


def test_archivo_existente_corrupto_se_rebaja(settings):
    dest = settings.beat_this_checkpoint_path
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"basura de tamano > 0")
    download = FakeDownloader()
    ensure_checkpoint(settings, download, sleep=no_sleep)
    assert dest.read_bytes() == b"pesos"
    assert download.urls == ["http://oficial/final0.ckpt"]


class GarbageDownloader(FakeDownloader):
    """Responde 200 con algo que no es un checkpoint (p. ej. una página de error)."""

    def __call__(self, url, dest):
        self.urls.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"<html>200 pero no es un checkpoint</html>")


def test_respuesta_200_que_no_es_checkpoint_se_descarta(settings):
    dest = settings.beat_this_checkpoint_path
    download = GarbageDownloader()

    def convert(source, out):
        out.write_bytes(b"tampoco")

    with pytest.raises(RuntimeError):
        ensure_checkpoint(settings, download, convert, sleep=no_sleep)
    assert not dest.exists()
    assert not list(dest.parent.glob("*.part")) and not list(dest.parent.glob("*.safetensors"))
    assert download.urls.count("http://oficial/final0.ckpt") == 3


def test_conversion_invalida_no_deja_archivo(settings):
    dest = settings.beat_this_checkpoint_path
    download = FakeDownloader(failing_urls=["http://oficial/final0.ckpt"])

    def convert(source, out):
        out.write_bytes(b"corrupto")

    with pytest.raises(RuntimeError):
        ensure_checkpoint(settings, download, convert, sleep=no_sleep)
    assert not dest.exists()
    assert not list(dest.parent.glob("*.part"))


def test_main_devuelve_error_si_falla(settings, monkeypatch, capsys):
    def boom(_settings):
        raise RuntimeError("sin red")

    monkeypatch.setattr(beat_this_weights, "ensure_checkpoint", boom)
    monkeypatch.setattr(sys, "argv", ["x"])
    assert beat_this_weights.main() == 1
    assert "sin red" in capsys.readouterr().err


@pytest.mark.skipif(importlib.util.find_spec("beat_this") is None, reason="falta beat_this")
def test_conversion_del_espejo_completa_los_buffers(tmp_path):
    import torch
    from beat_this.model.beat_tracker import BeatThis
    from safetensors.torch import save_file

    model_state = BeatThis().state_dict()
    persistent = {
        k: v.contiguous() for k, v in model_state.items() if "rotary_embed.freqs" not in k
    }
    source = tmp_path / "m.safetensors"
    save_file(persistent, str(source))
    dest = tmp_path / "m.ckpt"
    beat_this_weights.safetensors_to_ckpt(source, dest)
    ckpt = torch.load(dest, map_location="cpu", weights_only=True)
    assert set(ckpt["state_dict"]) == {f"model.{k}" for k in model_state}
