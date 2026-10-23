"""Reglas puras: qué patrones del catálogo sirven para un compás y un tempo.

- Compás: solo entran patrones con el mismo `beats_per_bar` (3/4 no recibe patrones de 4/4).
  Compases sin patrones en el catálogo (2, 5, 6, 7...) dan lista vacía: "sin datos".
- Tempo: cuanto más rápido, más simple el patrón (tope de complejidad por rango de bpm).
- Densidad de ataques (opcional): ataques por beat medidos en el audio. Si no se pasa, se apunta
  a una complejidad media. T12 no la calcula del audio; queda como entrada para afinar después.
"""

from collections.abc import Sequence

from guitarra_worker.strum.catalog import Pattern

# (bpm máximo, complejidad máxima). Por encima del último rango, solo complejidad 1.
COMPLEXITY_BY_TEMPO: tuple[tuple[float, int], ...] = ((90, 4), (120, 3), (150, 2))
FASTEST_MAX_COMPLEXITY = 1
TARGET_COMPLEXITY = 3


def max_complexity_for(bpm: float) -> int:
    for max_bpm, complexity in COMPLEXITY_BY_TEMPO:
        if bpm <= max_bpm:
            return complexity
    return FASTEST_MAX_COMPLEXITY


def attacks_per_beat(pattern: Pattern) -> float:
    attacks = sum(1 for char in pattern.pattern if char in "DUpima")
    return attacks / pattern.beats_per_bar


def candidate_patterns(
    catalog: Sequence[Pattern], kind: str, beats_per_bar: int, bpm: float
) -> list[Pattern]:
    limit = max_complexity_for(bpm)
    return [
        p
        for p in catalog
        if p.kind == kind and p.beats_per_bar == beats_per_bar and p.complexity <= limit
    ]


def default_pattern(candidates: Sequence[Pattern], density: float | None = None) -> Pattern | None:
    """El patrón que elegirían las reglas solas; determinista (desempata por complejidad e id)."""
    if not candidates:
        return None

    def distance(pattern: Pattern) -> float:
        if density is None:
            return abs(pattern.complexity - TARGET_COMPLEXITY)
        return abs(attacks_per_beat(pattern) - density)

    return min(candidates, key=lambda p: (distance(p), p.complexity, p.id))
