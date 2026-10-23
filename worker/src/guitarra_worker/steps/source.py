"""Paso 1: resolver la fuente (qué video de YouTube se analiza y cuáles son sus metadatos).

Salida: `{youtube_id, title, artist, duration_s, year, resolved_from}` donde `resolved_from` es
`youtube`, `spotify` o `search`.

Caché: si el trabajo llega con `youtube_id`, `song_dir` ya es `<cache>/<youtube_id>`. Si viene de
Spotify o de una búsqueda, el runner no conoce todavía el video y `song_dir` queda como
`<cache>/song-<id>`; ahí se guardan también el audio y los pasos siguientes. Alcanza porque la
canción tiene un solo `song_id` y el reintento reusa la misma carpeta.
"""

from typing import Any, Protocol

from guitarra_worker.adapters.spotify import TrackInfo
from guitarra_worker.adapters.youtube import VideoInfo
from guitarra_worker.domain.matching import Candidate, choose_youtube_candidate
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext

SEARCH_RESULTS = 10


class YoutubeSource(Protocol):
    def metadata(self, video_id: str) -> VideoInfo: ...

    def search(self, query: str, n: int = ...) -> list[Candidate]: ...


class SpotifySource(Protocol):
    def track(self, spotify_id: str) -> TrackInfo: ...


def _output(
    youtube_id: str,
    title: str,
    artist: str,
    duration_s: float | None,
    year: int | None,
    resolved_from: str,
) -> dict[str, Any]:
    return {
        "youtube_id": youtube_id,
        "title": title,
        "artist": artist,
        "duration_s": duration_s,
        "year": year,
        "resolved_from": resolved_from,
    }


def _not_found(title: str, artist: str) -> str:
    return (
        f"No encontré en YouTube una versión que coincida con «{title} — {artist}»; "
        "pegá el link directo"
    )


class SourceStep:
    name = "source"
    version = "1"

    def __init__(self, youtube: YoutubeSource, spotify: SpotifySource) -> None:
        self._youtube = youtube
        self._spotify = spotify

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        job = ctx.job
        if job.source == "youtube" and job.youtube_id:
            return self._from_youtube(job.youtube_id)
        if job.source == "spotify" and job.spotify_id:
            return self._from_spotify(job.spotify_id)
        if job.source == "search" and job.title:
            return self._from_search(job.title, job.artist or "")
        raise PermanentStepError(f"No sé resolver la fuente del trabajo (source={job.source!r})")

    def _from_youtube(self, youtube_id: str) -> dict[str, Any]:
        video = self._youtube.metadata(youtube_id)
        return _output(
            youtube_id, video.title, video.artist, video.duration_s, video.year, "youtube"
        )

    def _from_spotify(self, spotify_id: str) -> dict[str, Any]:
        track = self._spotify.track(spotify_id)
        candidates = self._youtube.search(f"{track.artist} - {track.title}", SEARCH_RESULTS)
        chosen = choose_youtube_candidate(track.title, track.artist, track.duration_s, candidates)
        if chosen is None:
            raise PermanentStepError(_not_found(track.title, track.artist))
        candidate = chosen[0]
        return _output(
            candidate.id, track.title, track.artist, candidate.duration_s, track.year, "spotify"
        )

    def _from_search(self, title: str, artist: str) -> dict[str, Any]:
        candidates = self._youtube.search(f"{title} {artist}".strip(), SEARCH_RESULTS)
        chosen = choose_youtube_candidate(title, artist, None, candidates)
        if chosen is None:
            raise PermanentStepError(_not_found(title, artist))
        candidate = chosen[0]
        return _output(candidate.id, title, artist, candidate.duration_s, None, "search")
