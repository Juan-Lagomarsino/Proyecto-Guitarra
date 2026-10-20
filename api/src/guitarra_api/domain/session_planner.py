"""Generador de la sesión del día: función pura, sin DB ni framework.

Reglas (docs/PLAN.md, Estudio; docs/fases/fase-1.md, F1-T06):
- Nivel actual: el primer nivel (por orden) con algún ejercicio nunca completado.
- Pendiente: ejercicio nunca completado o con mejor BPM < objetivo.
- Bloques en orden: calentamiento -> técnica -> riff -> improvisación.
- Sesión de ~20 min (+-5). Determinista para una misma semilla.
- Otras categorías solo entran como relleno final, cuando las propias se agotaron.
- `ExerciseInfo.type` se transporta para la UI y no entra en la lógica.
- El mínimo (objetivo - tolerancia) se intenta, pero no se garantiza si el material no alcanza.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

BLOCK_ORDER: tuple[str, ...] = ("warmup", "technique", "riff", "improvisation")
DEFAULT_TARGET_MINUTES = 20
DEFAULT_TOLERANCE_MINUTES = 5


@dataclass(frozen=True)
class ExerciseInfo:
    id: str
    level_order: int
    type: str
    category: str
    duration_min: int
    bpm_target: int | None = None


@dataclass(frozen=True)
class PlannedExercise:
    exercise: ExerciseInfo
    minutes: int


@dataclass(frozen=True)
class SessionBlock:
    category: str
    exercises: list[PlannedExercise]

    @property
    def minutes(self) -> int:
        return sum(e.minutes for e in self.exercises)


@dataclass(frozen=True)
class SessionPlan:
    blocks: list[SessionBlock]
    total_minutes: int


def is_pending(exercise: ExerciseInfo, history: Mapping[str, int]) -> bool:
    """Nunca completado, o con mejor BPM por debajo del objetivo."""
    best = history.get(exercise.id)
    if best is None:
        return True
    return exercise.bpm_target is not None and best < exercise.bpm_target


def current_level(exercises: Sequence[ExerciseInfo], history: Mapping[str, int]) -> int | None:
    """Primer nivel con ejercicios nunca completados; None si todo se completó."""
    never_done = [e.level_order for e in exercises if e.id not in history]
    return min(never_done) if never_done else None


def _priority(
    exercise: ExerciseInfo,
    block: str,
    level: int | None,
    history: Mapping[str, int],
) -> tuple[int, ...]:
    """Menor es mejor. Los empates se desempatan al azar con la semilla."""
    pending = is_pending(exercise, history)
    own = exercise.category == block
    at_level = level is not None and exercise.level_order == level
    if own and block == "warmup" and (level is None or exercise.level_order <= level):
        return (0, 0 if pending and at_level else 1)
    if own and pending:
        return (1, 0 if at_level else 1)
    if own:
        return (2,)
    if pending:
        return (3, 0 if at_level else 1)
    return (4,)


def _ordered_pool(
    block: str,
    exercises: Sequence[ExerciseInfo],
    level: int | None,
    history: Mapping[str, int],
    rng: random.Random,
) -> list[ExerciseInfo]:
    groups: dict[tuple[int, ...], list[ExerciseInfo]] = {}
    for exercise in exercises:
        groups.setdefault(_priority(exercise, block, level, history), []).append(exercise)
    pool: list[ExerciseInfo] = []
    for key in sorted(groups):
        rng.shuffle(groups[key])
        pool.extend(groups[key])
    return pool


def _take(pool: list[ExerciseInfo], used: set[str], room: int) -> ExerciseInfo | None:
    for exercise in pool:
        if exercise.id not in used and exercise.duration_min <= room:
            return exercise
    return None


def build_session(
    exercises: Sequence[ExerciseInfo],
    history: Mapping[str, int],
    seed: int,
    target_minutes: int = DEFAULT_TARGET_MINUTES,
    tolerance_minutes: int = DEFAULT_TOLERANCE_MINUTES,
) -> SessionPlan:
    """Arma la sesión del día. `history` es {exercise_id: mejor BPM completado}."""
    rng = random.Random(seed)
    usable = sorted((e for e in exercises if e.duration_min > 0), key=lambda e: e.id)
    level = current_level(usable, history)
    pools = {b: _ordered_pool(b, usable, level, history, rng) for b in BLOCK_ORDER}
    chosen: dict[str, list[ExerciseInfo]] = {b: [] for b in BLOCK_ORDER}
    used: set[str] = set()
    total = 0
    max_total = target_minutes + tolerance_minutes
    share = target_minutes / len(BLOCK_ORDER)

    def add(block: str, own_only: bool) -> bool:
        nonlocal total
        pool = [e for e in pools[block] if (e.category == block) == own_only]
        exercise = _take(pool, used, max_total - total)
        if exercise is None:
            return False
        chosen[block].append(exercise)
        used.add(exercise.id)
        total += exercise.duration_min
        return True

    def fill(blocks: Sequence[str], own_only: bool) -> None:
        progressed = True
        while total < target_minutes and progressed:
            progressed = False
            for block in blocks:
                if total < target_minutes and add(block, own_only):
                    progressed = True

    # Pasada 1: cada bloque con ejercicios de su propia categoría.
    for position, block in enumerate(BLOCK_ORDER, start=1):
        cumulative_goal = share * position
        while (not chosen[block] or total < cumulative_goal) and add(block, own_only=True):
            pass

    # Pasada 2: más ejercicios propios hasta el objetivo.
    fill(BLOCK_ORDER, own_only=True)
    # Pasada 3 (relleno final): otras categorías, empezando por los bloques vacíos.
    by_emptiness = sorted(BLOCK_ORDER, key=lambda b: bool(chosen[b]))
    fill(by_emptiness, own_only=False)

    blocks = [
        SessionBlock(b, [PlannedExercise(e, e.duration_min) for e in chosen[b]])
        for b in BLOCK_ORDER
        if chosen[b]
    ]
    return SessionPlan(blocks=blocks, total_minutes=total)
