"""Parseo puro de links de YouTube y Spotify hacia el identificador de la canción."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_SPOTIFY_ID = re.compile(r"[A-Za-z0-9]{22}")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}
_SPOTIFY_URI = re.compile(r"spotify:track:(?P<id>[A-Za-z0-9]{22})")
_LANGUAGE_PREFIX = re.compile(r"intl-[a-z]{2}(-[a-z]{2})?", re.IGNORECASE)


class InvalidSongUrlError(ValueError):
    """El link no es de un video de YouTube ni de un tema de Spotify."""


@dataclass(frozen=True)
class ParsedSongUrl:
    source: str
    youtube_id: str | None = None
    spotify_id: str | None = None


def parse_song_url(raw_url: str) -> ParsedSongUrl:
    text = raw_url.strip()
    uri = _SPOTIFY_URI.fullmatch(text)
    if uri:
        return ParsedSongUrl("spotify", spotify_id=uri["id"])
    try:
        url = urlparse(text if "://" in text else f"https://{text}")
        host = (url.hostname or "").lower()
    except ValueError as error:
        raise InvalidSongUrlError("El link no tiene un formato válido") from error
    segments = [segment for segment in url.path.split("/") if segment]
    if host in _YOUTUBE_HOSTS:
        return ParsedSongUrl("youtube", youtube_id=_youtube_id_from_site(url.query, segments))
    if host == "youtu.be":
        return ParsedSongUrl("youtube", youtube_id=_checked_youtube(segments[:1]))
    if host == "open.spotify.com":
        return ParsedSongUrl("spotify", spotify_id=_spotify_id(segments))
    raise InvalidSongUrlError("Solo se aceptan links de YouTube o de un tema de Spotify")


def _youtube_id_from_site(query: str, segments: list[str]) -> str:
    if segments[:1] == ["watch"]:
        return _checked_youtube(parse_qs(query).get("v", [])[:1])
    if segments[:1] == ["shorts"]:
        return _checked_youtube(segments[1:2])
    raise InvalidSongUrlError("El link de YouTube no apunta a un video")


def _checked_youtube(candidates: list[str]) -> str:
    if candidates and _YOUTUBE_ID.fullmatch(candidates[0]):
        return candidates[0]
    raise InvalidSongUrlError("El id del video de YouTube no es válido")


def _spotify_id(segments: list[str]) -> str:
    if segments and _LANGUAGE_PREFIX.fullmatch(segments[0]):
        segments = segments[1:]
    if len(segments) >= 2 and segments[0] == "track" and _SPOTIFY_ID.fullmatch(segments[1]):
        return segments[1]
    raise InvalidSongUrlError("Solo se aceptan links de un tema de Spotify (/track/<id>)")
