import shutil

import pytest

from guitarra_worker.adapters.spotify import TrackInfo
from guitarra_worker.adapters.youtube import VideoInfo
from guitarra_worker.api_client import Job
from guitarra_worker.domain.matching import Candidate
from guitarra_worker.pipeline.registry import default_steps
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext, RetryableStepError
from guitarra_worker.steps.download import DownloadStep
from guitarra_worker.steps.source import SourceStep
from wavs import make_wav


class FakeYoutube:
    def __init__(self, candidates=(), video=None, wav_seconds=10.0):
        self.candidates = list(candidates)
        self.video = video
        self.wav_seconds = wav_seconds
        self.queries = []
        self.downloads = []

    def metadata(self, video_id):
        return self.video

    def search(self, query, n=10):
        self.queries.append(query)
        return self.candidates

    def download_wav(self, video_id, dest, progress=None):
        self.downloads.append(video_id)
        make_wav(dest, seconds=self.wav_seconds, rate=48_000, channels=2)


class FakeSpotify:
    def __init__(self, track=None, error=None):
        self.track_info = track
        self.error = error

    def track(self, spotify_id):
        if self.error:
            raise self.error
        return self.track_info


def ctx_for(job, tmp_path, outputs=None):
    return PipelineContext(job=job, song_dir=tmp_path / "song", outputs=outputs or {})


def make_job(job, **changes):
    return Job.model_validate({**job.model_dump(), **changes})


def test_source_youtube(job, tmp_path):
    video = VideoInfo("abc123", "Wonderwall", "Oasis", 258, 1995)
    out = SourceStep(FakeYoutube(video=video), FakeSpotify()).run(ctx_for(job, tmp_path))
    assert out == {
        "youtube_id": "abc123",
        "title": "Wonderwall",
        "artist": "Oasis",
        "duration_s": 258,
        "year": 1995,
        "resolved_from": "youtube",
    }


def test_source_spotify_busca_por_artista_titulo_y_duracion(job, tmp_path):
    spotify_job = make_job(job, source="spotify", youtube_id=None, spotify_id="sp1")
    track = TrackInfo("Wonderwall", "Oasis", 258.7, 1995)
    youtube = FakeYoutube(
        candidates=[
            Candidate("live", "Oasis - Wonderwall (Live)", "Oasis", 258),
            Candidate("lejos", "Oasis - Wonderwall", "Oasis", 280),
            Candidate("ok", "Oasis - Wonderwall (Official Audio)", "Oasis", 259),
        ]
    )
    out = SourceStep(youtube, FakeSpotify(track)).run(ctx_for(spotify_job, tmp_path))
    assert youtube.queries == ["Oasis - Wonderwall"]
    assert out == {
        "youtube_id": "ok",
        "title": "Wonderwall",
        "artist": "Oasis",
        "duration_s": 259,
        "year": 1995,
        "resolved_from": "spotify",
    }


def test_source_spotify_sin_coincidencia_falla_sin_reintento(job, tmp_path):
    spotify_job = make_job(job, source="spotify", youtube_id=None, spotify_id="sp1")
    track = TrackInfo("Wonderwall", "Oasis", 258.7, 1995)
    step = SourceStep(FakeYoutube(), FakeSpotify(track))
    with pytest.raises(PermanentStepError, match="pegá el link"):
        step.run(ctx_for(spotify_job, tmp_path))


def test_source_spotify_sin_credenciales_propaga_el_error(job, tmp_path):
    spotify_job = make_job(job, source="spotify", youtube_id=None, spotify_id="sp1")
    step = SourceStep(FakeYoutube(), FakeSpotify(error=PermanentStepError("Faltan SPOTIFY")))
    with pytest.raises(PermanentStepError, match="Faltan SPOTIFY"):
        step.run(ctx_for(spotify_job, tmp_path))


def test_source_search_sin_duracion_objetivo(job, tmp_path):
    search_job = make_job(job, source="search", youtube_id=None, title="Wonderwall", artist="Oasis")
    youtube = FakeYoutube(candidates=[Candidate("v9", "Oasis - Wonderwall", "Oasis", 261)])
    out = SourceStep(youtube, FakeSpotify()).run(ctx_for(search_job, tmp_path))
    assert youtube.queries == ["Wonderwall Oasis"]
    assert (out["youtube_id"], out["duration_s"], out["resolved_from"]) == ("v9", 261, "search")
    assert (out["title"], out["artist"], out["year"]) == ("Wonderwall", "Oasis", None)


def test_source_search_sin_resultados(job, tmp_path):
    search_job = make_job(job, source="search", youtube_id=None, title="Nada", artist="Nadie")
    with pytest.raises(PermanentStepError):
        SourceStep(FakeYoutube(), FakeSpotify()).run(ctx_for(search_job, tmp_path))


def test_source_desconocida(job, tmp_path):
    weird = make_job(job, source=None, youtube_id=None)
    with pytest.raises(PermanentStepError):
        SourceStep(FakeYoutube(), FakeSpotify()).run(ctx_for(weird, tmp_path))


def test_download_descarga_valida_y_reporta(job, tmp_path):
    youtube = FakeYoutube(wav_seconds=10.0)
    messages = []
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 10}})
    ctx.progress = messages.append
    out = DownloadStep(youtube).run(ctx)
    assert youtube.downloads == ["abc123"]
    assert out == {
        "wav_path": str((tmp_path / "song" / "original.wav").resolve()),
        "sample_rate": 48_000,
        "channels": 2,
        "duration_s": 10.0,
    }
    assert messages


def test_download_reusa_el_wav_si_existe(job, tmp_path):
    youtube = FakeYoutube()
    make_wav(tmp_path / "song" / "original.wav", seconds=10, rate=48_000, channels=2)
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 10}})
    DownloadStep(youtube).run(ctx)
    assert youtube.downloads == []


def test_download_con_wav_corrupto_lo_baja_de_nuevo(job, tmp_path):
    youtube = FakeYoutube()
    broken = tmp_path / "song" / "original.wav"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(b"no soy un wav")
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 10}})
    DownloadStep(youtube).run(ctx)
    assert youtube.downloads == ["abc123"]


def test_download_con_duracion_distinta_es_reintentable_y_limpia(job, tmp_path):
    youtube = FakeYoutube(wav_seconds=2.0)
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 200}})
    with pytest.raises(RetryableStepError):
        DownloadStep(youtube).run(ctx)
    assert not (tmp_path / "song" / "original.wav").exists()


def test_download_sin_duracion_esperada_no_valida(job, tmp_path):
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": None}})
    assert DownloadStep(FakeYoutube(wav_seconds=1.0)).run(ctx)["duration_s"] == 1.0


def test_registro_en_orden_source_download_tempo():
    from guitarra_worker.config import Settings

    steps = default_steps(Settings(_env_file=None))
    assert [s.name for s in steps] == ["source", "download", "tempo", "structure", "strum"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg no está en el PATH")
def test_download_con_ffmpeg_real_y_yt_dlp_falso(job, tmp_path):
    from guitarra_worker.adapters.youtube import YoutubeAdapter
    from test_youtube import VIDEO, FakeYdl

    adapter = YoutubeAdapter(shutil.which("ffmpeg"), ydl_factory=lambda o: FakeYdl(o, VIDEO))
    ctx = ctx_for(job, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 0.5}})
    out = DownloadStep(adapter).run(ctx)
    assert (out["sample_rate"], out["channels"]) == (48_000, 2)


def test_download_duracion_distinta_en_segundo_intento_es_permanente(job, tmp_path):
    second = make_job(job, attempt=2)
    ctx = ctx_for(second, tmp_path, {"source": {"youtube_id": "abc123", "duration_s": 200}})
    with pytest.raises(PermanentStepError):
        DownloadStep(FakeYoutube(wav_seconds=2.0)).run(ctx)
