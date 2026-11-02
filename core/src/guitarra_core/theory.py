"""Teoría básica: notas, enarmonía y parseo de nombres de acordes.

Las notas se manejan como clases de altura (0 = C ... 11 = B). El nombre canónico usa
bemoles para Db, Eb, Ab y Bb, y sostenido para F#.
"""

import re
from dataclasses import dataclass, replace

NOTE_NAMES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
_NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTAL = {"#": 1, "♯": 1, "b": -1, "♭": -1}

# Distancias en semitonos desde la tónica.
INTERVAL_SEMITONES = {
    "1": 0,
    "b2": 1,
    "2": 2,
    "b3": 3,
    "3": 4,
    "4": 5,
    "b5": 6,
    "5": 7,
    "#5": 8,
    "6": 9,
    "b7": 10,
    "7": 11,
}

NO_CHORD_NAMES = frozenset({"N", "N.C.", "NC", "N.C"})

QUALITY_TRIAD = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "power": (0, 7),
}
_QUALITY_SUFFIX = {
    "maj": "",
    "min": "m",
    "dim": "dim",
    "aug": "aug",
    "sus2": "sus2",
    "sus4": "sus4",
    "power": "5",
}
_EXTENSION_ORDER = ("6", "7", "maj7", "9", "maj9", "add9", "b5", "#5")
_TOKENS = (
    "maj9", "maj7", "maj", "add9", "dim", "aug", "sus2", "sus4", "sus",
    "b5", "#5", "m", "5", "6", "7", "9",
)  # fmt: skip
_QUALITY_TOKENS = {
    "m": "min",
    "dim": "dim",
    "aug": "aug",
    "sus2": "sus2",
    "sus4": "sus4",
    "sus": "sus4",
    "5": "power",
}
_HARTE_BASS_INTERVAL = re.compile(r"^[b#]?\d+$")
_PITCH = re.compile(r"^([A-G])([#b♯♭]?)(\d)$")
_ROOT = re.compile(r"^([A-G])([#b♯♭]?)(.*)$", re.DOTALL)


class ChordParseError(ValueError):
    """El texto no es un acorde que el parser entienda."""


@dataclass(frozen=True)
class Chord:
    root: str
    quality: str  # maj | min | dim | aug | sus2 | sus4 | power
    extensions: tuple[str, ...] = ()
    bass: str | None = None

    @property
    def name(self) -> str:
        quality = _QUALITY_SUFFIX[self.quality]
        extensions = "".join(self.extensions)
        body = extensions + quality if self.quality.startswith("sus") else quality + extensions
        slash = f"/{self.bass}" if self.bass else ""
        return f"{self.root}{body}{slash}"


def parse_note(text: str) -> int:
    """Nombre de nota (C, A#, Bb, E#, Cb) a clase de altura."""
    match = _ROOT.match(text.strip())
    if not match or match.group(3):
        raise ChordParseError(f"nota inválida: {text!r}")
    letter, accidental, _ = match.groups()
    return (_NATURAL_PC[letter] + _ACCIDENTAL.get(accidental, 0)) % 12


def parse_pitch(text: str) -> int:
    """Nota con octava ("E2", "F#3") a número MIDI (C4 = 60)."""
    match = _PITCH.match(text.strip())
    if not match:
        raise ChordParseError(f"nota con octava inválida: {text!r}")
    letter, accidental, octave = match.groups()
    return (int(octave) + 1) * 12 + _NATURAL_PC[letter] + _ACCIDENTAL.get(accidental, 0)


def note_name(pitch_class: int) -> str:
    return NOTE_NAMES[pitch_class % 12]


def is_no_chord(text: str) -> bool:
    return text.strip() in NO_CHORD_NAMES


def parse_chord(text: str) -> Chord | None:
    """Parsea un nombre de acorde; devuelve None para "N" (sin acorde).

    Acepta alias de Cifra Club y de los detectores (`A:min`, `C7M`, `Cº`, `C(9)`...).
    """
    text = text.strip()
    if is_no_chord(text):
        return None
    match = _ROOT.match(text)
    if not match:
        raise ChordParseError(f"acorde inválido: {text!r}")
    letter, accidental, rest = match.groups()
    root_pc = (_NATURAL_PC[letter] + _ACCIDENTAL.get(accidental, 0)) % 12
    harte = rest.startswith(":")
    body, bass_text = _split_bass(rest[1:] if harte else rest)
    quality, extensions = _parse_suffix(body)
    bass = _parse_bass(bass_text, root_pc, harte)
    return Chord(note_name(root_pc), quality, extensions, bass)


def lenient_chord(text: str) -> Chord | None:
    """Mejor esfuerzo para nombres que `parse_chord` rechaza: raíz y mayor/menor."""
    match = _ROOT.match(text.strip())
    if not match:
        return None
    letter, accidental, rest = match.groups()
    pitch_class = (_NATURAL_PC[letter] + _ACCIDENTAL.get(accidental, 0)) % 12
    is_minor = rest.startswith("m") and not rest.startswith("maj")
    return Chord(note_name(pitch_class), "min" if is_minor else "maj")


def _split_bass(rest: str) -> tuple[str, str | None]:
    if "/" not in rest:
        return rest, None
    body, _, bass_text = rest.rpartition("/")
    if not bass_text:
        raise ChordParseError("bajo vacío después de '/'")
    return body, bass_text


def _parse_bass(bass_text: str | None, root_pc: int, harte: bool) -> str | None:
    if bass_text is None:
        return None
    if harte and _HARTE_BASS_INTERVAL.match(bass_text):
        if bass_text not in INTERVAL_SEMITONES:
            raise ChordParseError(f"intervalo de bajo desconocido: {bass_text!r}")
        return note_name(root_pc + INTERVAL_SEMITONES[bass_text])
    return note_name(parse_note(bass_text))


def _normalize_suffix(body: str) -> str:
    body = body.replace("º", "dim").replace("°", "dim").replace("ø", "m7b5")
    body = body.replace("Δ", "maj7").replace("hdim7", "m7b5").replace("min", "m")
    body = re.sub(r"7M", "maj7", body)
    body = re.sub(r"M(?=[79]|$)", "maj", body)
    body = body.replace("+", "aug")
    if body.startswith("-"):
        body = "m" + body[1:]
    return body.replace(" ", "")


def _flatten_parentheses(body: str) -> str:
    if "(" not in body and ")" not in body:
        return body
    match = re.fullmatch(r"([^()]*)\(([^()]*)\)", body)
    if not match:
        raise ChordParseError(f"paréntesis inválidos: {body!r}")
    main, inner = match.groups()
    parts = [p for p in inner.split(",") if p]
    for part in parts:
        if part == "9":
            part = "9" if "7" in main else "add9"
        main += part
    return main


def _tokenize(body: str) -> list[str]:
    tokens, position = [], 0
    while position < len(body):
        token = next((t for t in _TOKENS if body.startswith(t, position)), None)
        if token is None:
            raise ChordParseError(f"sufijo de acorde desconocido: {body!r}")
        tokens.append(token)
        position += len(token)
    return tokens


def _parse_suffix(body: str) -> tuple[str, tuple[str, ...]]:
    tokens = _tokenize(_flatten_parentheses(_normalize_suffix(body)))
    quality: str | None = None
    extensions: set[str] = set()
    for token in tokens:
        if token in _QUALITY_TOKENS:
            new_quality = _QUALITY_TOKENS[token]
            if quality not in (None, new_quality):
                raise ChordParseError(f"calidades contradictorias: {body!r}")
            quality = new_quality
        elif token != "maj":
            extensions.add(token)
    quality = quality or "maj"
    return quality, _merge_extensions(quality, extensions, body)


def _merge_extensions(quality: str, extensions: set[str], body: str) -> tuple[str, ...]:
    if "9" in extensions and "6" in extensions:
        raise ChordParseError(f"6/9 no soportado: {body!r}")
    if quality == "power" and extensions:
        raise ChordParseError(f"un power chord no lleva extensiones: {body!r}")
    if "9" in extensions and "maj7" in extensions:
        extensions -= {"9", "maj7"}
        extensions.add("maj9")
    if "maj9" in extensions:
        extensions -= {"maj7", "7", "9"}
    if "9" in extensions:
        extensions -= {"7", "add9"}
    return tuple(e for e in _EXTENSION_ORDER if e in extensions)


def pitch_classes(chord: Chord) -> frozenset[int]:
    """Clases de altura que tienen que sonar (incluye el bajo, si lo hay)."""
    intervals = set(QUALITY_TRIAD[chord.quality])
    for extension in chord.extensions:
        _apply_extension(intervals, chord.quality, extension)
    root = parse_note(chord.root)
    result = {(root + i) % 12 for i in intervals}
    if chord.bass:
        result.add(parse_note(chord.bass))
    return frozenset(result)


def _apply_extension(intervals: set[int], quality: str, extension: str) -> None:
    seventh = 9 if quality == "dim" else 10
    if extension in ("b5", "#5"):
        intervals.discard(7)
        intervals.add(INTERVAL_SEMITONES[extension])
        return
    additions = {
        "6": (9,),
        "7": (seventh,),
        "maj7": (11,),
        "9": (10, 2),
        "maj9": (11, 2),
        "add9": (2,),
    }[extension]
    intervals.update(additions)


def transpose_chord(chord: Chord, semitones: int) -> Chord:
    root = note_name(parse_note(chord.root) + semitones)
    bass = note_name(parse_note(chord.bass) + semitones) if chord.bass else None
    return replace(chord, root=root, bass=bass)


def without_bass(chord: Chord) -> Chord:
    return replace(chord, bass=None)


def simplifications(chord: Chord) -> list[Chord]:
    """Versiones cada vez más simples (sin bajo), para cuando no hay forma del acorde exacto."""
    base = without_bass(chord)
    kept = {"7": "7", "9": "7", "maj7": "maj7", "maj9": "maj7"}
    sevenths = {kept[e] for e in base.extensions if e in kept}
    steps = [
        replace(base, extensions=tuple(e for e in _EXTENSION_ORDER if e in sevenths)),
        replace(base, extensions=()),
    ]
    unique: list[Chord] = []
    for step in steps:
        if step != chord and step not in unique:
            unique.append(step)
    return unique
