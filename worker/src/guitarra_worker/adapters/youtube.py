"""Envoltorio de yt-dlp (usado como librería): metadatos, búsqueda y descarga a WAV."""

import tempfile
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from guitarra_worker.adapters import ffmpeg
from guitarra_worker.domain.matching import Candidate
from guitarra_worker.pipeline.step import PermanentStepError, ProgressCallback, RetryableStepError

WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
TOPIC_SUFFIX = " - Topic"

# Fragmentos (en minúsculas) de los mensajes de yt-dlp que reintentar no arregla.
PERMANENT_MARKERS = (
    "video unavailable",
    "private video",
    "this video is private",
    "has been removed",
    "no longer available",
    "account associated with this video has been terminated",
    "copyright",
    "not available in your country",
    "blocked it in your country",
    "confirm your age",
    "members-only",
)

YdlFactory = Callable[[dict[str, Any]], AbstractContextManager[Any]]
Converter = Callable[[str, Path, Path], None]


@dataclass(frozen=True)
class VideoInfo:
    id: str
    title: str
    artist: str
    duration_s: float | None
    year: int | None


def _classify(exc: Exception) -> Exception:
    """Convierte un error de yt-dlp o de red en el error de paso que corresponde."""
    message = str(exc)
    if any(marker in message.lower() for marker in PERMANENT_MARKERS):
        return PermanentStepError(f"YouTube: {message}")
    return RetryableStepError(f"YouTube: {message}")


def _clean_artist(name: str | None) -> str:
    name = (name or "").strip()
    return name.removesuffix(TOPIC_SUFFIX).strip()


def _year(info: dict[str, Any]) -> int | None:
    if info.get("release_year"):
        return int(info["release_year"])
    release_date = str(info.get("release_date") or "")
    return int(release_date[:4]) if release_date[:4].isdigit() else None


def _to_video_info(info: dict[str, Any]) -> VideoInfo:
    artist = (
        info.get("artist") or info.get("creator") or info.get("uploader") or info.get("channel")
    )
    return VideoInfo(
        id=info["id"],
        title=info.get("track") or info.get("title") or "",
        artist=_clean_artist(artist),
        duration_s=info.get("duration"),
        year=_year(info),
    )


def _to_candidate(entry: dict[str, Any]) -> Candidate:
    channel = entry.get("channel") or entry.get("uploader") or ""
    return Candidate(
        id=entry["id"],
        title=entry.get("title") or "",
        channel=channel,
        duration_s=entry.get("duration"),
    )


class YoutubeAdapter:
    def __init__(
        self,
        ffmpeg_path: str | None = None,
        *,
        ydl_factory: YdlFactory = yt_dlp.YoutubeDL,
        converter: Converter = ffmpeg.convert_to_wav,
    ) -> None:
        self._ffmpeg_path = ffmpeg_path
        self._ydl_factory = ydl_factory
        self._converter = converter

    def metadata(self, video_id: str) -> VideoInfo:
        info = self._extract(WATCH_URL.format(video_id=video_id), {"skip_download": True})
        return _to_video_info(info)

    def search(self, query: str, n: int = 10) -> list[Candidate]:
        info = self._extract(f"ytsearch{n}:{query}", {"extract_flat": "in_playlist"})
        entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
        return [_to_candidate(e) for e in entries]

    def download_wav(
        self, video_id: str, dest: Path, progress: ProgressCallback | None = None
    ) -> None:
        """Baja el mejor audio y lo deja en `dest` como WAV 48 kHz estéreo (escritura atómica)."""
        ffmpeg_path = ffmpeg.find_ffmpeg(self._ffmpeg_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent, prefix="dl-") as tmp:
            raw = self._download_audio(video_id, Path(tmp), progress, ffmpeg_path)
            self._converter(ffmpeg_path, raw, dest)

    def _download_audio(
        self, video_id: str, tmp: Path, progress: ProgressCallback | None, ffmpeg_path: str
    ) -> Path:
        options: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": str(tmp / "audio.%(ext)s"),
            "ffmpeg_location": ffmpeg_path,
        }
        if progress is not None:
            options["progress_hooks"] = [_progress_hook(progress)]
        self._extract(WATCH_URL.format(video_id=video_id), options, download=True)
        files = [f for f in tmp.iterdir() if f.is_file() and f.suffix != ".part"]
        if not files:
            raise RetryableStepError("YouTube: la descarga no dejó ningún archivo de audio")
        return files[0]

    def _extract(
        self, target: str, extra: dict[str, Any], download: bool = False
    ) -> dict[str, Any]:
        options = {
            "quiet": True,
            "noprogress": True,
            "no_warnings": True,
            "noplaylist": True,
            **extra,
        }
        try:
            with self._ydl_factory(options) as ydl:
                info = ydl.extract_info(target, download=download)
        except (DownloadError, ExtractorError, OSError) as exc:
            raise _classify(exc) from exc
        if not isinstance(info, dict):
            raise RetryableStepError("YouTube: respuesta vacía")
        return info


def _progress_hook(progress: ProgressCallback) -> Callable[[dict[str, Any]], None]:
    def hook(status: dict[str, Any]) -> None:
        if status.get("status") == "downloading":
            progress(f"Descargando audio: {str(status.get('_percent_str', '')).strip()}")

    return hook
