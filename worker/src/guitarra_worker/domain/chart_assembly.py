"""Armado de las secciones y los acordes del SongChart (lógica pura, sin pasos ni disco).

Junta lo detectado (BTC por tiempos, estructura por compases) con la cifra de Cifra Club cuando
la alineación es buena: los nombres salen de la cifra, los tiempos de lo detectado. Los esquemas
de salida son los de `api/.../domain/song_chart.py` (ADR 0008); el worker no importa la API, así
que acá se arman diccionarios y los tests los validan contra el modelo.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from guitarra_core.theory import is_no_chord, parse_chord, transpose_chord

from guitarra_worker.domain.alignment import Alignment, align, blend_confidence

GOOD_ALIGNMENT = 0.6  # similitud mínima para fiarse de los nombres de Cifra Club
MAJORITY = 0.5
TIME_DECIMALS = 3
WHOLE_SONG_NAME = "Canción"
MAX_SLUG_LENGTH = 60


@dataclass(frozen=True)
class DetectedChord:
    start: float
    end: float
    label: str
    confidence: float


@dataclass(frozen=True)
class SectionDraft:
    start_s: float
    end_s: float
    name: str | None
    group: str | None


@dataclass(frozen=True)
class ChordDraft:
    t_s: float
    name: str
    confidence: float
    from_cifra: bool


@dataclass(frozen=True)
class SectionPlan:
    """Una sección ya armada: nombre final, acordes y de dónde salieron los nombres."""

    name: str
    start_s: float
    end_s: float
    chords: list[ChordDraft]

    @property
    def chord_source(self) -> str:
        from_cifra = sum(1 for chord in self.chords if chord.from_cifra)
        return "cifraclub" if from_cifra > len(self.chords) * MAJORITY else "detected"


@dataclass(frozen=True)
class CifraMatch:
    """Correspondencia entre lo detectado y la cifra (por acorde detectado, el de la cifra)."""

    alignment: Alignment
    cifra_chords: list[str]
    cifra_sections: list[str]  # nombre de la sección de cada acorde de la cifra
    matches: dict[int, int]  # índice detectado -> índice de la cifra

    def chord_name(self, detected_index: int) -> str:
        name = self.cifra_chords[self.matches[detected_index]]
        shift = self.alignment.transposition
        return transpose_chord_name(name, shift) if shift else name

    def section_name_for(self, detected_indexes: list[int]) -> str | None:
        """Nombre de la sección de la cifra que concentra la mayoría de esos acordes."""
        names = [
            self.cifra_sections[self.matches[i]] for i in detected_indexes if i in self.matches
        ]
        if not names:
            return None
        top = max(set(names), key=names.count)
        return top if names.count(top) >= len(names) * MAJORITY else None


def transpose_chord_name(name: str, semitones: int) -> str:
    chord = parse_chord(name)
    return name if chord is None else transpose_chord(chord, semitones).name


def merge_detected(raw: list[dict[str, Any]]) -> list[DetectedChord]:
    """Pasa de la salida del paso de acordes a la lista sin silencios y sin repetidos seguidos."""
    merged: list[DetectedChord] = []
    previous_label: str | None = None
    for item in raw:
        label = item["label"]
        if not label or is_no_chord(label):
            previous_label = None
            continue
        chord = DetectedChord(item["start"], item["end"], label, item["confidence"])
        if merged and previous_label == label:
            merged[-1] = _joined(merged[-1], chord)
        else:
            merged.append(chord)
        previous_label = label
    return merged


def _joined(first: DetectedChord, second: DetectedChord) -> DetectedChord:
    first_len, second_len = first.end - first.start, second.end - second.start
    total = first_len + second_len
    confidence = (
        (first.confidence * first_len + second.confidence * second_len) / total
        if total > 0
        else first.confidence
    )
    return DetectedChord(first.start, second.end, first.label, confidence)


def section_drafts(structure: list[dict[str, Any]], song_end_s: float) -> list[SectionDraft]:
    """Secciones de la estructura sin solapes; si no hay ninguna, una sola con toda la canción."""
    drafts: list[SectionDraft] = []
    cursor = 0.0
    for item in sorted(structure, key=lambda s: s["start_s"]):
        start, end = max(item["start_s"], cursor), item["end_s"]
        if round(end, TIME_DECIMALS) <= round(start, TIME_DECIMALS):
            continue
        drafts.append(SectionDraft(start, end, item.get("name"), item.get("group")))
        cursor = end
    if drafts:
        return drafts
    if song_end_s <= 0:
        raise ValueError("no hay secciones ni duración para armar una sola sección")
    return [SectionDraft(0.0, song_end_s, WHOLE_SONG_NAME, None)]


def match_with_cifra(
    cifra: dict[str, Any] | None, detected: list[DetectedChord]
) -> CifraMatch | None:
    """None si no hay cifra, no hay acordes detectados o la alineación no es buena."""
    if not cifra or not cifra.get("found") or not detected:
        return None
    names = [chord for section in cifra["sections"] for chord in section["chords"]]
    section_names = [s["name"] for s in cifra["sections"] for _ in s["chords"]]
    alignment = align(names, [chord.label for chord in detected])
    if alignment.similarity < GOOD_ALIGNMENT:
        return None
    matches = {j: i for i, j in alignment.pairs if i is not None and j is not None}
    return CifraMatch(alignment, names, section_names, matches)


def _section_index(drafts: list[SectionDraft], chord: DetectedChord) -> int | None:
    """Sección donde cae el acorde; si empieza en un hueco, la siguiente si lo alcanza."""
    for index, draft in enumerate(drafts):
        if chord.start < draft.start_s:
            return index if chord.end > draft.start_s else None
        if chord.start < draft.end_s:
            return index
    return None


def _default_name(draft: SectionDraft, index: int) -> str:
    if draft.name:
        return draft.name
    return f"Parte {draft.group}" if draft.group else f"Sección {index + 1}"


def plan_sections(
    drafts: list[SectionDraft], detected: list[DetectedChord], match: CifraMatch | None
) -> list[SectionPlan]:
    members: list[list[int]] = [[] for _ in drafts]
    for position, chord in enumerate(detected):
        index = _section_index(drafts, chord)
        if index is not None:
            members[index].append(position)
    return [
        _plan(draft, index, members[index], detected, match) for index, draft in enumerate(drafts)
    ]


def _plan(
    draft: SectionDraft,
    index: int,
    positions: list[int],
    detected: list[DetectedChord],
    match: CifraMatch | None,
) -> SectionPlan:
    name = (match.section_name_for(positions) if match else None) or _default_name(draft, index)
    chords = [_chord_draft(detected[p], p, draft, match) for p in positions]
    return SectionPlan(name, draft.start_s, draft.end_s, _inside_section(chords, draft))


def _chord_draft(
    chord: DetectedChord, position: int, draft: SectionDraft, match: CifraMatch | None
) -> ChordDraft:
    t_s = max(chord.start, draft.start_s)
    if match and position in match.matches:
        confidence = blend_confidence(chord.confidence, match.alignment.similarity)
        return ChordDraft(t_s, match.chord_name(position), confidence, True)
    return ChordDraft(t_s, chord.label, chord.confidence, False)


def _inside_section(chords: list[ChordDraft], draft: SectionDraft) -> list[ChordDraft]:
    """Descarta los acordes que al redondear a milisegundos quedan en el borde final."""
    end = round(draft.end_s, TIME_DECIMALS)
    return [c for c in chords if round(c.t_s, TIME_DECIMALS) < end]


def section_id(name: str, index: int) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:MAX_SLUG_LENGTH] or "seccion"
    return f"{index + 1:02d}-{slug}"
