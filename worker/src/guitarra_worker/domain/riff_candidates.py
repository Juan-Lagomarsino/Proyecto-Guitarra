"""Elige las secciones donde vale la pena transcribir un riff (lógica pura).

Candidata = tiene al menos `MIN_NOTES` notas y es la intro o su polifonía media es baja
(una línea melódica, no acordes rasgueados). Los umbrales viven acá y en ningún otro lado.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from guitarra_worker.domain.quantize import TimedNote

MIN_NOTES = 8
MAX_MEAN_POLYPHONY = 1.6  # notas simultáneas promedio por ataque
SIMULTANEOUS_WINDOW_S = 0.05  # ataques a menos de esto cuentan como el mismo golpe
INTRO_PREFIX = "intro"


@dataclass(frozen=True)
class SectionSpan:
    id: str
    name: str
    start_s: float
    end_s: float


def mean_polyphony(notes: Sequence[TimedNote]) -> float:
    """Promedio de notas por ataque. Se mide en los ataques y no con los offsets (poco fiables)."""
    onsets = sorted(n.onset_s for n in notes)
    if not onsets:
        return 0.0
    attacks, cluster_start = 1, onsets[0]
    for onset in onsets[1:]:
        if onset - cluster_start > SIMULTANEOUS_WINDOW_S:
            attacks, cluster_start = attacks + 1, onset
    return len(onsets) / attacks


def _is_intro(section: SectionSpan) -> bool:
    return section.name.strip().lower().startswith(INTRO_PREFIX)


def _is_candidate(section: SectionSpan, notes: Sequence[TimedNote]) -> bool:
    if len(notes) < MIN_NOTES:
        return False
    return _is_intro(section) or mean_polyphony(notes) <= MAX_MEAN_POLYPHONY


def choose_candidates(sections: Sequence[SectionSpan], notes: Sequence[TimedNote]) -> list[str]:
    """Ids de las secciones candidatas; cada nota pertenece a la sección de su ataque."""
    chosen = []
    for section in sections:
        inside = [n for n in notes if section.start_s <= n.onset_s < section.end_s]
        if _is_candidate(section, inside):
            chosen.append(section.id)
    return chosen
