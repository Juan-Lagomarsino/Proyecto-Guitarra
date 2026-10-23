import shutil
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from guitarra_worker.adapters.ffmpeg import read_wav_info
from guitarra_worker.adapters.youtube import YoutubeAdapter
from guitarra_worker.domain.matching import Candidate
from guitarra_worker.pipeline.step import PermanentStepError, RetryableStepError
from wavs import make_wav

VIDEO = {
    "id": "abc123",
    "title": "Wonderwall (Remastered)",
    "uploader": "Oasis - Topic",
    "duration": 258,
    "release_year": 1995,
}
SEARCH = {
    "entries": [
        {"id": "v1", "title": "Oasis - Wonderwall", "channel": "Oasis", "duration": 259},
        {"id": "v2", "title": "Sin duración", "uploader": "X", "duration": None},
        None,
    ]
}


class FakeYdl:
    """Doble de yt_dlp.YoutubeDL: registra opciones y devuelve respuestas grabadas."""

    instances: list["FakeYdl"] = []

    def __init__(self, options, response=None, error=None):
        self.options = options
        self.response = response
        self.error = error
        self.targets = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, target, download=False):
        self.targets.append((target, download))
        if self.error:
            raise self.error
        if download:
            for hook in self.options.get("progress_hooks", []):
                hook({"status": "downloading", "_percent_str": " 50.0%"})
            outtmpl = self.options["outtmpl"].replace("%(ext)s", "webm")
            make_wav(Path(outtmpl), seconds=0.5)
        return self.response


def adapter_with(response=None, error=None, converter=None):
    created = []

    def factory(options):
        ydl = FakeYdl(options, response, error)
        created.append(ydl)
        return ydl

    kwargs = {"converter": converter} if converter else {}
    return YoutubeAdapter("ffmpeg-falso", ydl_factory=factory, **kwargs), created


def test_metadata_toma_titulo_artista_duracion_y_anio():
    adapter, created = adapter_with(VIDEO)
    info = adapter.metadata("abc123")
    assert (info.id, info.title, info.artist) == ("abc123", "Wonderwall (Remastered)", "Oasis")
    assert (info.duration_s, info.year) == (258, 1995)
    assert created[0].targets == [("https://www.youtube.com/watch?v=abc123", False)]
    assert created[0].options["skip_download"] is True


def test_metadata_sin_anio_ni_artista_musical():
    adapter, _ = adapter_with({"id": "x", "title": "T", "channel": "Canal", "duration": 10})
    info = adapter.metadata("x")
    assert (info.artist, info.year) == ("Canal", None)


def test_search_devuelve_candidatos_y_descarta_entradas_vacias():
    adapter, created = adapter_with(SEARCH)
    result = adapter.search("oasis wonderwall", n=5)
    assert result == [
        Candidate("v1", "Oasis - Wonderwall", "Oasis", 259),
        Candidate("v2", "Sin duración", "X", None),
    ]
    assert created[0].targets == [("ytsearch5:oasis wonderwall", False)]


@pytest.mark.parametrize(
    "message",
    ["ERROR: [youtube] abc: Video unavailable", "Private video. Sign in", "has been removed"],
)
def test_video_no_disponible_o_privado_no_se_reintenta(message):
    adapter, _ = adapter_with(error=DownloadError(message))
    with pytest.raises(PermanentStepError):
        adapter.metadata("abc")


def test_error_de_red_es_reintentable():
    adapter, _ = adapter_with(error=DownloadError("Unable to download webpage: timed out"))
    with pytest.raises(RetryableStepError):
        adapter.search("x")


def test_oserror_es_reintentable():
    adapter, _ = adapter_with(error=ConnectionResetError("reset"))
    with pytest.raises(RetryableStepError):
        adapter.metadata("x")


def test_download_wav_convierte_y_escribe_atomico(tmp_path):
    calls = []

    def converter(ffmpeg_path, source, dest):
        calls.append((ffmpeg_path, source.suffix))
        shutil.copy(source, dest)

    adapter, _ = adapter_with(VIDEO, converter=converter)
    messages = []
    dest = tmp_path / "song" / "original.wav"
    adapter.download_wav("abc123", dest, progress=messages.append)
    assert dest.exists()
    assert calls == [("ffmpeg-falso", ".webm")]
    assert messages == ["Descargando audio: 50.0%"]
    assert [p.name for p in dest.parent.iterdir()] == ["original.wav"]  # sin temporales


def test_download_wav_con_error_no_deja_archivos(tmp_path):
    adapter, _ = adapter_with(error=DownloadError("HTTP Error 503"))
    dest = tmp_path / "song" / "original.wav"
    with pytest.raises(RetryableStepError):
        adapter.download_wav("abc", dest)
    assert list(dest.parent.iterdir()) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_download_wav_con_ffmpeg_real(tmp_path):
    def factory(options):
        return FakeYdl(options, VIDEO)

    adapter = YoutubeAdapter(shutil.which("ffmpeg"), ydl_factory=factory)
    dest = tmp_path / "original.wav"
    adapter.download_wav("abc123", dest)
    info = read_wav_info(dest)
    assert (info.sample_rate, info.channels) == (48_000, 2)
