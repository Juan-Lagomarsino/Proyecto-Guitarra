"""Alineación de la cifra por sección (lógica pura).

Hay cifras que escriben cada sección una sola vez ("Verso: G D Em C") y la canción las repite
muchas veces. Alinear la secuencia entera contra la detectada no funciona ahí (similitud ~0.1).
Acá se compara el ciclo de acordes de cada sección de la cifra contra los acordes detectados de
cada sección del audio: el ciclo se repite hasta cubrir la sección detectada, con la mejor rotación.

La transposición es una sola para toda la canción (la misma que impone el capo de la cifra):
se prueba primero 0, después la del capo, y se queda con la que más acordes empareja bien.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from guitarra_worker.domain.alignment import SEMITONES, align, transpose_chord

GOOD_SECTION_MATCH = 0.6  # similitud mínima de una sección para fiarse de los nombres de la cifra
MIN_SECTION_CHORDS = 3  # con menos acordes detectados no hay forma de comparar un ciclo
TIE_EPSILON = 1e-9

CifraSection = tuple[str, Sequence[str]]  # (nombre, acordes)


@dataclass(frozen=True)
class SectionMatch:
    """Cómo una sección detectada coincide con una de la cifra."""

    cifra_name: str
    similarity: float
    # (índice local del acorde detectado, nombre del acorde de la cifra ya transpuesto)
    chords: list[tuple[int, str]]


def minimal_cycle(chords: Sequence[str]) -> list[str]:
    """Prefijo más corto que, repetido, reproduce la lista (la última vuelta puede quedar corta)."""
    for size in range(1, len(chords) + 1):
        if all(chords[i] == chords[i % size] for i in range(len(chords))):
            return list(chords[:size])
    return list(chords)


def _tile(cycle: Sequence[str], rotation: int, length: int) -> list[str]:
    return [cycle[(rotation + i) % len(cycle)] for i in range(length)]


def _rotations(cycle: Sequence[str], section_size: int) -> range:
    """Un ciclo que no se repite en la sección se compara tal cual; uno que sí, con cada giro."""
    return range(len(cycle)) if len(cycle) < section_size else range(1)


def _shifted(names: Sequence[str], shift: int, rename: Callable[[str, int], str]) -> list[str]:
    return [rename(name, shift) if shift else name for name in names]


def _best_alignment(
    cycle: Sequence[str],
    labels: Sequence[str],
    shift: int,
    rename: Callable[[str, int], str],
) -> tuple[float, list[tuple[int, str]]]:
    """(similitud, [(índice detectado, acorde de la cifra)]) de la mejor rotación del ciclo."""
    best_similarity, best_pairs = -1.0, []
    for rotation in _rotations(cycle, len(labels)):
        tiled = _tile(cycle, rotation, len(labels))
        result = align(
            _shifted(tiled, shift, transpose_chord), list(labels), allow_transposition=False
        )
        if result.similarity > best_similarity:
            pairs = [
                (j, rename(tiled[i], shift) if shift else tiled[i])
                for i, j in result.pairs
                if i is not None and j is not None
            ]
            best_similarity, best_pairs = result.similarity, pairs
    return best_similarity, best_pairs


def _candidate_shifts(capo: int) -> list[int]:
    """Transposiciones a probar: ninguna, la del capo y el resto por cercanía a cero."""
    capo_shift = capo % SEMITONES
    capo_shift = capo_shift - SEMITONES if capo_shift > SEMITONES // 2 else capo_shift
    ordered = [0, capo_shift, *sorted(range(-5, 7), key=abs)]
    return list(dict.fromkeys(ordered))


def _match_section(
    labels: Sequence[str],
    cycles: Sequence[tuple[str, list[str]]],
    shift: int,
    rename: Callable[[str, int], str],
    uses: dict[str, int],
) -> SectionMatch | None:
    scored = [(name, *_best_alignment(cycle, labels, shift, rename)) for name, cycle in cycles]
    top = max(similarity for _, similarity, _ in scored)
    if top < GOOD_SECTION_MATCH:
        return None
    # Con empate (dos secciones con la misma progresión) se reparten en orden de aparición.
    tied = [item for item in scored if item[1] >= top - TIE_EPSILON]
    name, similarity, chords = min(tied, key=lambda item: uses.get(item[0], 0))
    return SectionMatch(name, similarity, chords)


def _match_all(
    sections: Sequence[Sequence[str] | None],
    cycles: Sequence[tuple[str, list[str]]],
    shift: int,
    rename: Callable[[str, int], str],
) -> list[SectionMatch | None]:
    uses: dict[str, int] = {}
    matches: list[SectionMatch | None] = []
    for labels in sections:
        found = _match_section(labels, cycles, shift, rename, uses) if labels else None
        if found:
            uses[found.cifra_name] = uses.get(found.cifra_name, 0) + 1
        matches.append(found)
    return matches


def _covered(sections: Sequence[Sequence[str] | None], matches: list[SectionMatch | None]) -> float:
    """Acordes detectados que cayeron en una sección bien emparejada, ponderado por similitud."""
    return sum(
        len(labels) * match.similarity
        for labels, match in zip(sections, matches, strict=True)
        if labels and match
    )


def match_sections(
    cifra_sections: Sequence[CifraSection],
    detected_sections: Sequence[Sequence[str]],
    capo: int,
    rename: Callable[[str, int], str],
) -> list[SectionMatch | None]:
    """Una coincidencia (o None) por sección detectada.

    `detected_sections` trae los nombres de acorde detectados de cada sección; las que tienen
    menos de MIN_SECTION_CHORDS no se comparan. `rename(nombre, semitonos)` transpone el nombre
    del acorde que sale en el chart (el que usa el resto del armado).
    """
    cycles = [(name, minimal_cycle(chords)) for name, chords in cifra_sections if chords]
    comparable = [s if len(s) >= MIN_SECTION_CHORDS else None for s in detected_sections]
    if not cycles or not any(comparable):
        return [None] * len(detected_sections)
    best: list[SectionMatch | None] = [None] * len(detected_sections)
    best_score = 0.0
    for shift in _candidate_shifts(capo):
        matches = _match_all(comparable, cycles, shift, rename)
        score = _covered(comparable, matches)
        if score > best_score + TIE_EPSILON:
            best, best_score = matches, score
    return best
