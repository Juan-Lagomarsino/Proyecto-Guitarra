"""Elección del resultado de YouTube que corresponde a una canción. Función pura, sin red."""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

DURATION_TOLERANCE_S = 3.0
MIN_TITLE_COVERAGE = 0.7  # sobre las palabras significativas (sin stopwords)
MIN_ARTIST_COVERAGE = 0.5
MIN_SCORE = 0.6
STOPWORDS = frozenset(
    "a al con de del el en la las lo los no o por the un una y s t of and to in".split()
)

# Versiones que no queremos como base de análisis, salvo que estén en el título buscado.
UNWANTED_PHRASES = (
    "live",
    "unplugged",
    "mtv",
    "session",
    "sesion en vivo",
    "en vivo",
    "cover",
    "karaoke",
    "acustico",
    "acustica",
    "acoustic",
    "remix",
    "instrumental",
    "tribute",
    "tutorial",
    "lesson",
    "leccion",
    "reaction",
    "nightcore",
    "slowed",
    "sped up",
    "8d audio",
)
OFFICIAL_AUDIO_BONUS = 0.25
ARTIST_CHANNEL_BONUS = 0.15


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    channel: str
    duration_s: float | None


def normalize(text: str) -> str:
    """Minúsculas, sin tildes ni signos; palabras separadas por un espacio."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


def _contains_phrase(normalized: str, phrase: str) -> bool:
    return f" {phrase} " in f" {normalized} "


def _coverage(target: str, haystack: str) -> float:
    """Fracción de las palabras significativas de `target` presentes en `haystack`."""
    words = [w for w in target.split() if w not in STOPWORDS]
    if not words:
        return 1.0
    present = set(haystack.split())
    return sum(word in present for word in words) / len(words)


def _is_unwanted(candidate_text: str, target_text: str) -> bool:
    return any(
        _contains_phrase(candidate_text, phrase) and not _contains_phrase(target_text, phrase)
        for phrase in UNWANTED_PHRASES
    )


def _official_bonus(title: str, channel: str, artist: str) -> float:
    bonus = 0.0
    if _contains_phrase(title, "official audio") or channel.endswith(" topic"):
        bonus += OFFICIAL_AUDIO_BONUS
    if artist and artist in channel:
        bonus += ARTIST_CHANNEL_BONUS
    return bonus


def _duration_closeness(target: float | None, actual: float | None) -> float:
    """1.0 si coinciden, 0.0 en el borde de la tolerancia."""
    if target is None or actual is None:
        return 0.0
    return max(0.0, 1.0 - abs(target - actual) / DURATION_TOLERANCE_S)


def _within_duration(target: float | None, actual: float | None) -> bool:
    if target is None:
        return True
    return actual is not None and abs(target - actual) <= DURATION_TOLERANCE_S


def _score(
    target_title: str, target_artist: str, target_duration_s: float | None, candidate: Candidate
) -> float | None:
    title = normalize(candidate.title)
    channel = normalize(candidate.channel)
    title_coverage = _coverage(target_title, title)
    if title_coverage < MIN_TITLE_COVERAGE:
        return None
    artist_coverage = _coverage(target_artist, f"{title} {channel}")
    if target_artist and artist_coverage < MIN_ARTIST_COVERAGE:
        return None
    similarity = SequenceMatcher(None, f"{target_artist} {target_title}", title).ratio()
    score = (
        0.5 * title_coverage
        + 0.2 * artist_coverage
        + 0.1 * similarity
        + 0.1 * _duration_closeness(target_duration_s, candidate.duration_s)
        + _official_bonus(title, channel, target_artist)
    )
    return score if score >= MIN_SCORE else None


def choose_youtube_candidate(
    target_title: str,
    target_artist: str,
    target_duration_s: float | None,
    candidates: list[Candidate],
) -> tuple[Candidate, float] | None:
    """Devuelve (candidato, score) o None si ninguno sirve.

    Filtra por duración (±3 s) cuando hay duración objetivo y descarta versiones no deseadas
    (live, cover, karaoke...) salvo que figuren en el título buscado. El score va de 0 a 1.5.
    """
    title = normalize(target_title)
    artist = normalize(target_artist)
    best: tuple[Candidate, float] | None = None
    for candidate in candidates:
        if not _within_duration(target_duration_s, candidate.duration_s):
            continue
        if _is_unwanted(normalize(candidate.title), title):
            continue
        score = _score(title, artist, target_duration_s, candidate)
        if score is not None and (best is None or score > best[1]):
            best = (candidate, score)
    return best
