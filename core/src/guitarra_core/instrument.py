"""Adaptación de una progresión al instrumento: capo (clásica) y power chords (eléctrica)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from guitarra_core.chord_shapes import ChordShape, shape_position, shapes_for
from guitarra_core.theory import (
    Chord,
    ChordParseError,
    is_no_chord,
    lenient_chord,
    parse_chord,
    transpose_chord,
)

Instrument = Literal["classical", "electric"]
INSTRUMENTS = ("classical", "electric")

DEFAULT_MAX_CAPO = 7
CAPO_FRET_PENALTY = 0.25  # a igual dificultad, mejor el capo más bajo
JUMP_PENALTY_PER_FRET = 0.5  # costo de mover la mano entre acordes consecutivos
NO_CHORD = "N"


@dataclass(frozen=True)
class CapoSuggestion:
    capo: int
    forms: list[str]  # acordes "de forma": lo que se toca con ese capo
    cost: float


@dataclass(frozen=True)
class Voicing:
    chord: str  # el acorde tal como suena en la canción
    form: str  # el acorde cuya forma se toca (distinto con capo o power chord)
    shape: ChordShape | None  # None para "N" o si no hay forma posible


def best_capo(progression: Sequence[str], max_capo: int = DEFAULT_MAX_CAPO) -> CapoSuggestion:
    """Capo que minimiza la dificultad total de la progresión en guitarra clásica."""
    best: CapoSuggestion | None = None
    for capo in range(max_capo + 1):
        cost = capo_cost(progression, capo)
        if best is None or cost < best.cost:
            best = CapoSuggestion(capo, capo_forms(progression, capo), cost)
    return best or CapoSuggestion(0, capo_forms(progression, 0), 0.0)


def capo_forms(progression: Sequence[str], capo: int) -> list[str]:
    return [_transposed_name(name, -capo) for name in progression]


def capo_cost(progression: Sequence[str], capo: int) -> float:
    """Dificultad total de tocar la progresión con ese capo (la forma más fácil de cada acorde)."""
    total = CAPO_FRET_PENALTY * capo
    for form in capo_forms(progression, capo):
        shapes = shapes_for(form)
        if shapes:
            total += min(shape.difficulty for shape in shapes)
    return total


def voicings_for(
    progression: Sequence[str], instrument: Instrument, capo: int, power_chords: bool
) -> list[Voicing]:
    """Elige una forma por acorde, cuidando que la mano no salte lejos entre acordes."""
    if instrument not in INSTRUMENTS:
        raise ValueError(f"instrumento desconocido: {instrument!r}")
    use_power = instrument == "electric" and power_chords
    entries = [_entry(name, capo, use_power) for name in progression]
    chosen = _choose_coherent([candidates for _, _, candidates in entries])
    return [
        Voicing(chord, form, shape) for (chord, form, _), shape in zip(entries, chosen, strict=True)
    ]


def _entry(name: str, capo: int, use_power: bool) -> tuple[str, str, tuple[ChordShape, ...]]:
    written = _canonical_name(name)
    form = _transposed_name(name, -capo)
    if use_power:
        form = _as_power_chord(form)
    return written, form, shapes_for(form)


def _canonical_name(name: str) -> str:
    chord = _read(name)
    return chord.name if chord else (NO_CHORD if is_no_chord(name) else name.strip())


def _read(name: str) -> Chord | None:
    try:
        return parse_chord(name)
    except ChordParseError:
        return lenient_chord(name)


def _transposed_name(name: str, semitones: int) -> str:
    if is_no_chord(name):
        return NO_CHORD
    chord = _read(name)
    if chord is None:
        return name.strip()
    return transpose_chord(chord, semitones).name if semitones else _canonical_name(name)


def _as_power_chord(form: str) -> str:
    chord = _read(form)
    if chord and chord.quality in ("maj", "min") and not chord.extensions:
        return f"{chord.root}5"
    return form


def _choose_coherent(candidates_per_chord: list[tuple[ChordShape, ...]]) -> list[ChordShape | None]:
    """Viterbi: minimiza dificultad más saltos de posición entre acordes consecutivos."""
    slots = [i for i, candidates in enumerate(candidates_per_chord) if candidates]
    chosen: list[ChordShape | None] = [None] * len(candidates_per_chord)
    if not slots:
        return chosen
    costs = [s.difficulty for s in candidates_per_chord[slots[0]]]
    back: list[list[int]] = []
    for previous, current in zip(slots, slots[1:], strict=False):
        costs, pointers = _advance(
            costs, candidates_per_chord[previous], candidates_per_chord[current]
        )
        back.append(pointers)
    index = min(range(len(costs)), key=costs.__getitem__)
    for position in reversed(range(len(slots))):
        chosen[slots[position]] = candidates_per_chord[slots[position]][index]
        if position > 0:
            index = back[position - 1][index]
    return chosen


def _advance(
    costs: list[float], previous: tuple[ChordShape, ...], current: tuple[ChordShape, ...]
) -> tuple[list[float], list[int]]:
    new_costs, pointers = [], []
    for shape in current:
        options = [
            cost
            + JUMP_PENALTY_PER_FRET * abs(shape_position(shape.shape) - shape_position(p.shape))
            for cost, p in zip(costs, previous, strict=True)
        ]
        best = min(range(len(options)), key=options.__getitem__)
        new_costs.append(options[best] + shape.difficulty)
        pointers.append(best)
    return new_costs, pointers
