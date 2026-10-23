"""Alineación entre la secuencia de acordes de Cifra Club y la detectada del audio.

Lógica pura: distancia de edición ponderada (un acorde con la misma raíz pero otra
calidad cuesta menos que uno con otra raíz), con búsqueda de transposición (capo,
afinación distinta) y mezcla de confianza.
"""

import re
from dataclasses import dataclass

SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_CHORD = re.compile(r"^([A-G])([#b]?)([^/]*)(?:/([A-G])([#b]?))?$")

SAME_ROOT_COST = 0.5  # misma raíz, otra calidad (o bajo): casi acertó
INDEL_COST = 1.0
SEMITONES = 12


@dataclass(frozen=True)
class Chord:
    root: int
    quality: str
    bass: int | None = None


def _pitch_class(letter: str, accidental: str) -> int:
    shift = {"#": 1, "b": -1, "": 0}[accidental]
    return (_NATURAL_PC[letter] + shift) % SEMITONES


def parse_chord(name: str) -> Chord | None:
    """None si no es un acorde reconocible (p. ej. 'N.C.')."""
    match = _CHORD.match(name.strip())
    if not match:
        return None
    letter, accidental, quality, bass_letter, bass_acc = match.groups()
    bass = _pitch_class(bass_letter, bass_acc) if bass_letter else None
    return Chord(_pitch_class(letter, accidental), quality, bass)


def _format(chord: Chord) -> str:
    text = SHARP_NAMES[chord.root] + chord.quality
    return text if chord.bass is None else f"{text}/{SHARP_NAMES[chord.bass]}"


def transpose_chord(name: str, semitones: int) -> str:
    """Transpone un acorde (devuelve sostenidos). Si no se reconoce, lo deja igual."""
    chord = parse_chord(name)
    if chord is None:
        return name
    bass = None if chord.bass is None else (chord.bass + semitones) % SEMITONES
    return _format(Chord((chord.root + semitones) % SEMITONES, chord.quality, bass))


def _shift(chord: Chord, semitones: int) -> Chord:
    bass = None if chord.bass is None else (chord.bass + semitones) % SEMITONES
    return Chord((chord.root + semitones) % SEMITONES, chord.quality, bass)


def _substitution_cost(a: Chord, b: Chord) -> float:
    if a == b:
        return 0.0
    return SAME_ROOT_COST if a.root == b.root else 1.0


@dataclass(frozen=True)
class Alignment:
    """pairs: (índice en Cifra Club, índice en lo detectado); None = omisión o inserción."""

    transposition: int
    distance: float
    similarity: float
    pairs: list[tuple[int | None, int | None]]


def _edit_matrix(a: list[Chord], b: list[Chord]) -> list[list[float]]:
    m = [[0.0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        m[i][0] = i * INDEL_COST
    for j in range(1, len(b) + 1):
        m[0][j] = j * INDEL_COST
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            m[i][j] = min(
                m[i - 1][j - 1] + _substitution_cost(a[i - 1], b[j - 1]),
                m[i - 1][j] + INDEL_COST,
                m[i][j - 1] + INDEL_COST,
            )
    return m


def _trace(
    m: list[list[float]], a: list[Chord], b: list[Chord]
) -> list[tuple[int | None, int | None]]:
    pairs: list[tuple[int | None, int | None]] = []
    i, j = len(a), len(b)
    while i > 0 or j > 0:
        if i > 0 and j > 0 and m[i][j] == m[i - 1][j - 1] + _substitution_cost(a[i - 1], b[j - 1]):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif i > 0 and m[i][j] == m[i - 1][j] + INDEL_COST:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    pairs.reverse()
    return pairs


def _readable(names: list[str]) -> list[tuple[int, Chord]]:
    parsed = ((i, parse_chord(n)) for i, n in enumerate(names))
    return [(i, c) for i, c in parsed if c is not None]


def _align_at(
    cifra: list[tuple[int, Chord]], detected: list[tuple[int, Chord]], shift: int
) -> Alignment:
    a = [_shift(c, shift) for _, c in cifra]
    b = [c for _, c in detected]
    matrix = _edit_matrix(a, b)
    distance = matrix[len(a)][len(b)]
    longest = max(len(a), len(b))
    similarity = 1.0 - distance / longest if longest else 0.0
    pairs = [
        (None if i is None else cifra[i][0], None if j is None else detected[j][0])
        for i, j in _trace(matrix, a, b)
    ]
    return Alignment(shift, distance, max(similarity, 0.0), pairs)


def align(cifra: list[str], detected: list[str], *, allow_transposition: bool = True) -> Alignment:
    """Alinea la secuencia de Cifra Club con la detectada.

    Con `allow_transposition` prueba los 12 semitonos y se queda con el de menor distancia
    (a igualdad, el de menor desplazamiento). `transposition` es lo que hay que sumarle a
    Cifra Club para que suene como lo detectado. Los acordes ilegibles se ignoran.
    """
    left, right = _readable(cifra), _readable(detected)
    shifts = sorted(range(-5, 7), key=abs) if allow_transposition else [0]
    candidates = [_align_at(left, right, s) for s in shifts]
    return min(candidates, key=lambda r: (r.distance, abs(r.transposition)))


def blend_confidence(detected_confidence: float, similarity: float) -> float:
    """Sube la confianza de lo detectado si Cifra Club coincide y la baja si no.

    Similitud 0.5 no cambia nada; 1.0 cierra la mitad de lo que falta para 1; 0.0 le
    saca la mitad. Siempre queda en [0, 1].
    """
    c = min(max(detected_confidence, 0.0), 1.0)
    if similarity >= 0.5:
        return c + (similarity - 0.5) * (1.0 - c)
    return c - (0.5 - similarity) * c
