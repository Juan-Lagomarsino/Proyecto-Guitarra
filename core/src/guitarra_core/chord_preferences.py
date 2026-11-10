"""Formas de acorde preferidas: qué forma eligió el usuario para cada acorde, por instrumento.

Pura: sin I/O. Se compara el chart de referencia (el vigente antes de la edición) con el del
usuario; si un acorde conserva su nombre y su momento pero cambia la forma, esa es una elección.

Clave canónica de la forma (`shape_key`): los trastes en **altura absoluta** (traste del chart +
capo, cuerdas mudas "x"), 6 valores de la 6ta a la 1ra separados por coma, p. ej. `"x,3,2,0,1,0"`.
Se eligió absoluta y no relativa al capo porque la forma relativa depende del capo de cada canción:
"A con la forma de G abierto" con capo 2 es la misma digitación real que `5,4,2,2,2,5` sin capo.
Con la absoluta, la preferencia "para el acorde A, esta digitación" sirve en una canción con otro
capo: quien la use resta su capo (`absoluta - capo`) y la descarta si algún traste queda < 0.

JSON: `{instrumento: {acorde_canónico: {shape_key: peso}}}`, pesos en (0, 1].
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from guitarra_core.theory import ChordParseError, parse_chord

EMA_ALPHA = 0.3  # peso de la última elección frente a lo acumulado (igual que la digitación)
MIN_WEIGHT = 0.02  # por debajo se poda: lo viejo que no se repitió se olvida
SAME_MOMENT_TOLERANCE_S = 0.01
MUTED = "x"

Json = Mapping[str, Any]


@dataclass(frozen=True)
class ShapeChoice:
    chord: str  # nombre canónico
    shape_key: str


def shape_key(shape: Sequence[int | str], capo: int) -> str:
    return ",".join(MUTED if fret == MUTED else str(int(fret) + capo) for fret in shape)


def to_relative(key: str, capo: int) -> tuple[int | str, ...] | None:
    """Inversa de `shape_key`: la forma para ese capo, o None si no se puede tocar con él.

    Una cuerda al aire absoluta (0) con capo > 0 no es aplicable: el capo la subiría.
    """
    frets: list[int | str] = []
    for part in key.split(","):
        if part == MUTED:
            frets.append(MUTED)
            continue
        fret = int(part) - capo
        if fret < 0:
            return None
        frets.append(fret)
    return tuple(frets)


def canonical_chord_name(name: str) -> str | None:
    """Nombre normalizado del acorde (`A:min` y `Am` coinciden); None si no es un acorde."""
    try:
        chord = parse_chord(name)
    except ChordParseError:
        return None
    return None if chord is None else chord.name


def chosen_shapes(reference: Json, edited: Json) -> list[ShapeChoice]:
    """Elecciones de forma del usuario: mismo acorde, mismo momento y sección, otra forma."""
    reference_chords = _chords_by_section(reference)
    choices: list[ShapeChoice] = []
    for section_id, chords in _chords_by_section(edited).items():
        for t_s, name, key in chords:
            before = _find(reference_chords.get(section_id, []), t_s)
            if before is not None and before[0] == name and before[1] != key:
                choices.append(ShapeChoice(name, key))
    return choices


def _chords_by_section(chart: Json) -> dict[str, list[tuple[float, str, str]]]:
    capo = int(chart.get("capo") or 0)
    result: dict[str, list[tuple[float, str, str]]] = {}
    for section in chart.get("sections", []):
        entries = []
        for chord in section.get("chords", []):
            name = canonical_chord_name(chord["name"])
            if name is not None:
                entries.append((float(chord["t_s"]), name, shape_key(chord["shape"], capo)))
        result[section["id"]] = entries
    return result


def _find(chords: list[tuple[float, str, str]], t_s: float) -> tuple[str, str] | None:
    for time, name, key in chords:
        if abs(time - t_s) <= SAME_MOMENT_TOLERANCE_S:
            return name, key
    return None


@dataclass(frozen=True)
class ChordShapePreferences:
    weights: Mapping[str, Mapping[str, Mapping[str, float]]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Json | None) -> "ChordShapePreferences":
        return cls(
            {
                instrument: {
                    chord: {key: float(w) for key, w in shapes.items()}
                    for chord, shapes in chords.items()
                }
                for instrument, chords in (data or {}).items()
            }
        )

    def to_json(self) -> dict[str, Any]:
        return {
            instrument: {
                chord: {key: round(w, 6) for key, w in sorted(shapes.items())}
                for chord, shapes in sorted(chords.items())
            }
            for instrument, chords in sorted(self.weights.items())
        }

    def learn(self, instrument: str, choices: Sequence[ShapeChoice]) -> "ChordShapePreferences":
        """Cada elección acerca su forma a 1 y deja caer las otras del mismo acorde (EMA)."""
        updated = {
            name: {c: dict(s) for c, s in chords.items()} for name, chords in self.weights.items()
        }
        chords = updated.setdefault(instrument, {})
        for choice in choices:
            chords[choice.chord] = _after_choice(chords.get(choice.chord, {}), choice.shape_key)
        return ChordShapePreferences(updated if choices else dict(self.weights))


def _after_choice(shapes: Mapping[str, float], chosen: str) -> dict[str, float]:
    decayed = {key: w * (1 - EMA_ALPHA) for key, w in shapes.items()}
    decayed[chosen] = decayed.get(chosen, 0.0) + EMA_ALPHA
    return {key: min(w, 1.0) for key, w in decayed.items() if w >= MIN_WEIGHT}
