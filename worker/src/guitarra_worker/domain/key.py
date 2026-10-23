"""Tonalidad por Krumhansl-Schmuckler sobre el histograma de acordes (lógica pura).

Se acumula, por clase de altura, cuánto tiempo suena cada nota de las tríadas de los acordes
detectados y se busca la tonalidad cuyo perfil (Krumhansl-Kessler, 1982) correlaciona más.
Confunde tonalidades relativas (mayor/menor), así que la confianza tiene techo y se informa la
relativa como alternativa.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import sqrt

from guitarra_core.theory import (
    QUALITY_TRIAD,
    Chord,
    ChordParseError,
    note_name,
    parse_chord,
    parse_note,
)

from guitarra_worker.domain.chords import NO_CHORD, ChordSpan

MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
KEY_CONFIDENCE_CAP = 0.6  # ADR 0006: KS sobre acordes acierta la tónica pero confunde relativas


@dataclass(frozen=True)
class DetectedKey:
    tonic: str
    mode: str  # "major" | "minor"
    confidence: float
    relative: str

    @property
    def name(self) -> str:
        return self.tonic + ("m" if self.mode == "minor" else "")


def detect_key(spans: Sequence[ChordSpan]) -> DetectedKey | None:
    """Tonalidad más probable, o None si no hay acordes (silencio) o el histograma es plano."""
    histogram = _histogram(spans)
    best: tuple[float, int, bool] | None = None
    for tonic in range(12):
        for minor, profile in ((False, MAJOR_PROFILE), (True, MINOR_PROFILE)):
            r = _correlation(histogram, _rotate(profile, tonic))
            if r is not None and (best is None or r > best[0]):
                best = (r, tonic, minor)
    if best is None:
        return None
    r, tonic, minor = best
    relative_tonic = (tonic + (3 if minor else -3)) % 12
    relative = note_name(relative_tonic) + ("" if minor else "m")
    return DetectedKey(
        note_name(tonic),
        "minor" if minor else "major",
        min(KEY_CONFIDENCE_CAP, max(0.0, r)),
        relative,
    )


def _histogram(spans: Sequence[ChordSpan]) -> list[float]:
    histogram = [0.0] * 12
    for span in spans:
        chord = _parse_or_none(span.label)
        if chord is None:
            continue
        root = parse_note(chord.root)
        for interval in QUALITY_TRIAD[chord.quality]:
            histogram[(root + interval) % 12] += span.end - span.start
    return histogram


def _parse_or_none(label: str) -> Chord | None:
    """Acorde del core; "N" o una etiqueta ilegible (caché corrupta) cuentan como sin acorde."""
    if label == NO_CHORD:
        return None
    try:
        return parse_chord(label)
    except ChordParseError:
        return None


def _rotate(profile: Sequence[float], semitones: int) -> list[float]:
    return [profile[(i - semitones) % 12] for i in range(12)]


def _correlation(a: Sequence[float], b: Sequence[float]) -> float | None:
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return None
    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    return covariance / sqrt(var_a * var_b)
