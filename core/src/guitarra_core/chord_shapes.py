"""Diccionario de acordes: de nombre de acorde a formas candidatas en la guitarra.

Una forma es una tupla de 6 elementos de la 6ta a la 1ra cuerda: traste (0-24) o "x".
Las formas abiertas salen de una tabla curada; el resto se genera desplazando formas
móviles (E-shape y A-shape con cejilla) y power chords. Toda forma suena exactamente
las notas del acorde que declara en `chord`.
"""

from dataclasses import dataclass, replace
from functools import lru_cache

from guitarra_core.theory import (
    Chord,
    ChordParseError,
    is_no_chord,
    lenient_chord,
    parse_chord,
    parse_note,
    simplifications,
    without_bass,
)

MUTED = "x"
OPEN_STRING_PITCH_CLASSES = (4, 9, 2, 7, 11, 4)  # afinación estándar, 6ta a 1ra
NUM_STRINGS = 6
MAX_ADDED_BASS_FRET = 5
MAX_SPAN = 4
MIN_STRINGS_FOR_INVERSION = 3

Fret = int | str
Frets = tuple[Fret, ...]

KIND_OPEN = "open"
KIND_BARRE = "barre"
KIND_POWER = "power"
KIND_MOVABLE = "movable"

FALLBACK_NO_BASS = "sin_bajo"
FALLBACK_SIMPLIFIED = "simplificado"

CURATED_SHAPES: dict[str, tuple[str, ...]] = {
    "C": ("x32010",),
    "D": ("xx0232",),
    "E": ("022100",),
    "G": ("320003", "320033"),
    "A": ("x02220",),
    "Am": ("x02210",),
    "Dm": ("xx0231",),
    "Em": ("022000",),
    "A7": ("x02020",),
    "B7": ("x21202",),
    "D7": ("xx0212",),
    "E7": ("020100",),
    "G7": ("320001",),
    "Am7": ("x02010",),
    "Dm7": ("xx0211",),
    "Em7": ("022030", "020000"),
    "Cmaj7": ("x32000",),
    "Dmaj7": ("xx0222",),
    "Fmaj7": ("xx3210",),
    "Gmaj7": ("320002",),
    "Amaj7": ("x02120",),
    "Emaj7": ("021100",),
    "Asus2": ("x02200",),
    "Asus4": ("x02230",),
    "Dsus2": ("xx0230",),
    "Dsus4": ("xx0233",),
    "Esus4": ("022200",),
    "Csus2": ("x30033",),
    "Csus4": ("x33011",),
    "Gsus4": ("330013",),
    "Cadd9": ("x32030",),
    "Gadd9": ("320203",),
    "Aadd9": ("x02420",),
    "A6": ("x02222",),
    "E6": ("022120",),
    "G6": ("320000",),
    "E9": ("020102",),
    "Bdim": ("x2343x",),
    "Ddim": ("xx0131",),
    "C/G": ("332010",),
    "C/E": ("032010",),
    "C/B": ("x22010",),
    "D/F#": ("200232",),
    "Am/E": ("002210",),
    "Am/G": ("302210",),
    "G/B": ("x20003",),
    "Em/B": ("x22000",),
}

# Formas móviles: desplazamientos respecto del traste `f` de la tónica (None = cuerda muteada).
_X = None
_E_SHAPES: dict[str, tuple[int | None, ...]] = {
    "": (0, 2, 2, 1, 0, 0),
    "m": (0, 2, 2, 0, 0, 0),
    "7": (0, 2, 0, 1, 0, 0),
    "m7": (0, 2, 0, 0, 0, 0),
    "maj7": (0, 2, 1, 1, 0, 0),
    "sus4": (0, 2, 2, 2, 0, 0),
    "7sus4": (0, 2, 0, 2, 0, 0),
    "6": (0, 2, 2, 1, 2, 0),
    "9": (0, 2, 0, 1, 0, 2),
    "aug": (0, 3, 2, 1, 1, 0),
}
_A_SHAPES: dict[str, tuple[int | None, ...]] = {
    "": (_X, 0, 2, 2, 2, 0),
    "m": (_X, 0, 2, 2, 1, 0),
    "7": (_X, 0, 2, 0, 2, 0),
    "m7": (_X, 0, 2, 0, 1, 0),
    "maj7": (_X, 0, 2, 1, 2, 0),
    "sus2": (_X, 0, 2, 2, 0, 0),
    "sus4": (_X, 0, 2, 2, 3, 0),
    "7sus4": (_X, 0, 2, 0, 3, 0),
    "6": (_X, 0, 2, 2, 2, 2),
    "add9": (_X, 0, 2, 4, 2, 0),
    "dim": (_X, 0, 1, 2, 1, _X),
    "dim7": (_X, 0, 1, 2, 1, 2),
    "m7b5": (_X, 0, 1, 0, 1, _X),
}
_E_ROOT_STRING_PC = OPEN_STRING_PITCH_CLASSES[0]
_A_ROOT_STRING_PC = OPEN_STRING_PITCH_CLASSES[1]


@dataclass(frozen=True)
class Barre:
    fret: int
    from_string: int  # cuerda más grave de la cejilla (6 = la más grave)
    to_string: int  # cuerda más aguda de la cejilla


@dataclass(frozen=True)
class ChordShape:
    name: str  # acorde pedido, en nombre canónico
    chord: str  # acorde que suena realmente (distinto de `name` si hay `fallback`)
    shape: Frets
    barre: Barre | None
    fingers: tuple[int, ...]  # 0 = cuerda al aire o muteada; 1 a 4 = dedo
    kind: str
    difficulty: float
    fallback: str | None = None

    def to_notation(self) -> dict:
        """Campos `shape` y `barre` con la forma del modelo `Chord` de la notación."""
        barre = None
        if self.barre:
            barre = {
                "fret": self.barre.fret,
                "from_string": self.barre.from_string,
                "to_string": self.barre.to_string,
            }
        return {"shape": list(self.shape), "barre": barre}


def shape_pitch_classes(shape: Frets) -> frozenset[int]:
    return frozenset(
        (OPEN_STRING_PITCH_CLASSES[i] + fret) % 12 for i, fret in enumerate(shape) if fret != MUTED
    )


def lowest_pitch_class(shape: Frets) -> int | None:
    index = _lowest_sounded_index(shape)
    if index is None:
        return None
    return (OPEN_STRING_PITCH_CLASSES[index] + shape[index]) % 12


def _lowest_sounded_index(shape: Frets) -> int | None:
    return next((i for i, fret in enumerate(shape) if fret != MUTED), None)


def shape_position(shape: Frets) -> float:
    """Posición media en el mástil (0 si es todo al aire); sirve para medir saltos."""
    frets = [f for f in shape if isinstance(f, int) and f > 0]
    return sum(frets) / len(frets) if frets else 0.0


# ---------------------------------------------------------------- construcción


def _covered_indices(frets: Frets, barre: Barre | None) -> set[int]:
    if barre is None:
        return set()
    return {
        i
        for i in range(NUM_STRINGS)
        if barre.to_string <= NUM_STRINGS - i <= barre.from_string and frets[i] == barre.fret
    }


def _assign_fingers(frets: Frets, barre: Barre | None) -> tuple[int, ...]:
    covered = _covered_indices(frets, barre)
    fingers = [0] * NUM_STRINGS
    for index in covered:
        fingers[index] = 1
    pressed = sorted(
        (fret, i)
        for i, fret in enumerate(frets)
        if isinstance(fret, int) and fret > 0 and i not in covered
    )
    next_finger = 2 if barre else 1
    for _, index in pressed:
        fingers[index] = min(next_finger, 4)
        next_finger += 1
    return tuple(fingers)


def _estimate_difficulty(frets: Frets, barre: Barre | None, kind: str) -> float:
    covered = _covered_indices(frets, barre)
    positive = [f for f in frets if isinstance(f, int) and f > 0]
    pressed = len([i for i, f in enumerate(frets) if isinstance(f, int) and f > 0]) - len(covered)
    span = max(positive) - min(positive) if positive else 0
    barre_cost = 1.0 + 0.4 * (barre.from_string - barre.to_string + 1) if barre else 0.0
    reach = 0.1 * (min(positive) - 1) if positive else 0.0
    difficulty = 0.25 + 0.5 * pressed + barre_cost + 0.5 * max(0, span - 2) + reach
    return round(difficulty * (0.7 if kind == KIND_POWER else 1.0), 3)


def _build(name: str, frets: Frets, barre: Barre | None, kind: str) -> ChordShape:
    return ChordShape(
        name=name,
        chord=name,
        shape=frets,
        barre=barre,
        fingers=_assign_fingers(frets, barre),
        kind=kind,
        difficulty=_estimate_difficulty(frets, barre, kind),
    )


def _parse_shape(text: str) -> Frets:
    return tuple(MUTED if char == MUTED else int(char) for char in text)


def _curated(chord: Chord) -> list[ChordShape]:
    return [
        _build(chord.name, _parse_shape(text), None, KIND_OPEN)
        for text in CURATED_SHAPES.get(chord.name, ())
    ]


def _suffix(chord: Chord) -> str:
    return chord.name[len(chord.root) :]


def _barre_for(offsets: tuple[int | None, ...], fret: int) -> Barre | None:
    zeros = [i for i, offset in enumerate(offsets) if offset == 0]
    if fret < 1 or len(zeros) < 2:
        return None
    return Barre(fret, NUM_STRINGS - min(zeros), NUM_STRINGS - max(zeros))


def _movable_from(
    chord: Chord, templates: dict[str, tuple[int | None, ...]], root_string_pc: int
) -> list[ChordShape]:
    offsets = templates.get(_suffix(chord))
    if offsets is None:
        return []
    fret = (parse_note(chord.root) - root_string_pc) % 12
    frets = tuple(MUTED if o is None else fret + o for o in offsets)
    barre = _barre_for(offsets, fret)
    kind = KIND_OPEN if fret == 0 else KIND_BARRE if barre else KIND_MOVABLE
    return [_build(chord.name, frets, barre, kind)]


def _power(chord: Chord) -> list[ChordShape]:
    root = parse_note(chord.root)
    e_fret = (root - _E_ROOT_STRING_PC) % 12
    a_fret = (root - _A_ROOT_STRING_PC) % 12
    forms = [
        (e_fret, e_fret + 2, e_fret + 2, MUTED, MUTED, MUTED),
        (MUTED, a_fret, a_fret + 2, a_fret + 2, MUTED, MUTED),
    ]
    return [_build(chord.name, frets, None, KIND_POWER) for frets in forms]


def _without_bass_candidates(chord: Chord) -> list[ChordShape]:
    shapes = _curated(chord)
    if chord.quality == "power":
        return shapes + _power(chord)
    shapes += _movable_from(chord, _E_SHAPES, _E_ROOT_STRING_PC)
    shapes += _movable_from(chord, _A_SHAPES, _A_ROOT_STRING_PC)
    return shapes


def _extended_barre(shape: ChordShape, index: int, fret: int) -> Barre | None:
    """Cejilla de la forma tras sumar la cuerda `index` al fret `fret`."""
    barre = shape.barre
    if barre and fret == barre.fret and index == NUM_STRINGS - barre.from_string - 1:
        return Barre(barre.fret, NUM_STRINGS - index, barre.to_string)
    return barre


def _shrunk_barre(shape: ChordShape, first_sounded: int) -> Barre | None:
    """Cejilla de la forma tras mutear las cuerdas anteriores a `first_sounded`."""
    barre = shape.barre
    if barre is None:
        return None
    from_string = min(barre.from_string, NUM_STRINGS - first_sounded)
    if from_string <= barre.to_string:
        return None
    return Barre(barre.fret, from_string, barre.to_string)


def _with_muted_below_bass(shape: ChordShape, bass_pc: int, chord_name: str) -> ChordShape | None:
    """Pone la nota del bajo como la más grave muteando las cuerdas graves, sin perder notas."""
    for index in range(NUM_STRINGS):
        fret = shape.shape[index]
        if fret == MUTED or (OPEN_STRING_PITCH_CLASSES[index] + fret) % 12 != bass_pc:
            continue
        frets = (MUTED,) * index + shape.shape[index:]
        sounded = [f for f in frets if f != MUTED]
        if len(sounded) < MIN_STRINGS_FOR_INVERSION:
            return None
        if shape_pitch_classes(frets) != shape_pitch_classes(shape.shape):
            return None
        barre = _shrunk_barre(shape, index)
        kind = KIND_MOVABLE if shape.kind == KIND_BARRE and barre is None else shape.kind
        return _build(chord_name, frets, barre, kind)
    return None


def _with_added_bass(shape: ChordShape, bass_pc: int, chord_name: str) -> ChordShape | None:
    """Suma el bajo en la cuerda grave contigua, si la forma no la usa."""
    lowest = _lowest_sounded_index(shape.shape)
    if lowest is None or lowest == 0:
        return None
    index = lowest - 1
    fret = (bass_pc - OPEN_STRING_PITCH_CLASSES[index]) % 12
    if fret > MAX_ADDED_BASS_FRET or not _bass_is_playable(shape, fret):
        return None
    frets = shape.shape[:index] + (fret,) + shape.shape[index + 1 :]
    return _build(chord_name, frets, _extended_barre(shape, index, fret), shape.kind)


def _add_bass(shape: ChordShape, bass_pc: int, chord_name: str) -> list[ChordShape]:
    if lowest_pitch_class(shape.shape) == bass_pc:
        return [_relabel(shape, chord_name, chord_name, shape.fallback)]
    options = (_with_muted_below_bass, _with_added_bass)
    results = [option(shape, bass_pc, chord_name) for option in options]
    return [r for r in results if r]


def _bass_is_playable(shape: ChordShape, fret: int) -> bool:
    if shape.barre and 0 < fret < shape.barre.fret:
        return False
    positive = [f for f in shape.shape if isinstance(f, int) and f > 0]
    if fret > 0:
        positive.append(fret)
    return not positive or max(positive) - min(positive) <= MAX_SPAN


def _with_bass_candidates(chord: Chord) -> list[ChordShape]:
    bass_pc = parse_note(chord.bass)
    shapes = _curated(chord)
    for base in _without_bass_candidates(without_bass(chord)):
        shapes.extend(_add_bass(base, bass_pc, chord.name))
    return shapes


def _relabel(shape: ChordShape, name: str, chord: str, fallback: str | None) -> ChordShape:
    return replace(shape, name=name, chord=chord, fallback=fallback)


def _dedupe_and_sort(shapes: list[ChordShape]) -> list[ChordShape]:
    unique: dict[Frets, ChordShape] = {}
    for shape in shapes:
        unique.setdefault(shape.shape, shape)
    return sorted(unique.values(), key=lambda s: (s.difficulty, str(s.shape)))


def _candidates(chord: Chord) -> list[ChordShape]:
    shapes = _with_bass_candidates(chord) if chord.bass else _without_bass_candidates(chord)
    return _dedupe_and_sort(shapes)


def _fallback_candidates(chord: Chord) -> tuple[list[ChordShape], str | None]:
    if chord.bass:
        shapes = _candidates(without_bass(chord))
        if shapes:
            return shapes, FALLBACK_NO_BASS
    for simpler in simplifications(chord):
        shapes = _candidates(simpler)
        if shapes:
            return shapes, FALLBACK_SIMPLIFIED
    return [], None


@lru_cache(maxsize=4096)
def shapes_for(name: str) -> tuple[ChordShape, ...]:
    """Formas candidatas de un acorde, de la más fácil a la más difícil.

    Vacío para "N" o para lo que no se puede leer ni como raíz y mayor/menor. Si no existe
    una forma del acorde exacto, devuelve las del acorde sin bajo o simplificado, con
    `fallback` marcado.
    """
    requested = name.strip()
    if is_no_chord(requested):
        return ()
    try:
        chord = parse_chord(requested)
    except ChordParseError:
        chord = lenient_chord(requested)
        if chord is None:
            return ()
        return _labelled(_candidates(chord), requested, FALLBACK_SIMPLIFIED)
    shapes = _candidates(chord)
    if shapes:
        return _labelled(shapes, chord.name, None)
    fallback_shapes, fallback = _fallback_candidates(chord)
    return _labelled(fallback_shapes, chord.name, fallback)


def _labelled(shapes: list[ChordShape], name: str, fallback: str | None) -> tuple[ChordShape, ...]:
    return tuple(_relabel(s, name, s.chord, fallback) for s in shapes)
