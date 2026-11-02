"""Digitación de una secuencia de notas: cuerda y traste por nota, por programación dinámica.

Es Viterbi sobre las combinaciones factibles de cada paso (un paso = una o más notas
simultáneas). El costo mezcla movimiento de la mano, cambio de cuerda, estiramiento, cuerdas al
aire, trastes altos y un bonus por las preferencias aprendidas. Pura: sin I/O.

Convenciones (las mismas que el formato de notación):
- Cuerdas numeradas como en la guitarra: 1 = la más aguda, 6 = la más grave (en afinación estándar).
- Las afinaciones se pasan de grave a aguda, como alturas MIDI.
- Los trastes se cuentan desde el capo: traste 0 = cuerda "al aire" con el capo puesto.
- La mano se modela con un solo número por paso: el traste más bajo que se pisa (el dedo índice).
  Un paso con todas las cuerdas al aire no mueve la mano: conserva la posición anterior.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

STANDARD_TUNING = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
DEFAULT_MAX_FRET = 22
MAX_CHORD_SPAN = 4  # trastes de diferencia entre notas pisadas de un mismo paso
# Tope de combinaciones por paso. Medido: un paso real tiene como mucho ~23 combinaciones
# válidas (el span <= 4 poda casi todo), así que el tope es solo una red de seguridad.
MAX_STATES_PER_STEP = 200
ZONE_WIDTH = 4  # trastes por zona de mano: zona = traste // ZONE_WIDTH

# Costos (todos en un solo lugar; FingeringCosts los usa como valores por defecto).
HAND_SHIFT_PER_FRET = 0.2  # desplazar la mano, por traste
HAND_REACH = 3  # trastes que se alcanzan sin mover la mano
HAND_SHIFT_BEYOND_REACH = 1.0  # extra por cada traste que pasa del alcance
STRING_CHANGE_PER_STRING = 0.15  # saltar de cuerda, por cuerda de distancia
CHORD_STRETCH_PER_FRET = 0.3  # abrir la mano dentro de un acorde, por traste de span
OPEN_STRING = 0.3  # tocar una cuerda al aire (positivo = menos preferida)
OPEN_LOW_REGISTER_BONUS = 0.5  # descuento si la nota es grave (el al aire suena bien abajo)
OPEN_LOW_REGISTER_MAX_MIDI = 52  # hasta Mi3 inclusive cuenta como registro grave
HIGH_FRET_START = 4  # desde acá cada traste cuesta un poco más
HIGH_FRET_PER_FRET = 0.15
POSITION_PREFERENCE_BONUS = 4.0  # bonus por nota con peso 1.0 en `positions`
ZONE_PREFERENCE_BONUS = 1.0  # bonus por nota pisada con peso 1.0 en `zones`

_EPSILON = 1e-12


class FingeringError(ValueError):
    """No hay digitación posible."""


class UnplayableNoteError(FingeringError):
    def __init__(self, pitch: int, index: int) -> None:
        super().__init__(
            f"La nota MIDI {pitch} (paso {index}) no se puede tocar con esta afinación, capo y "
            "rango de trastes"
        )
        self.pitch = pitch
        self.index = index


@dataclass(frozen=True)
class FingeringCosts:
    hand_shift_per_fret: float = HAND_SHIFT_PER_FRET
    hand_reach: int = HAND_REACH
    hand_shift_beyond_reach: float = HAND_SHIFT_BEYOND_REACH
    string_change_per_string: float = STRING_CHANGE_PER_STRING
    chord_stretch_per_fret: float = CHORD_STRETCH_PER_FRET
    open_string: float = OPEN_STRING
    open_low_register_bonus: float = OPEN_LOW_REGISTER_BONUS
    high_fret_start: int = HIGH_FRET_START
    high_fret_per_fret: float = HIGH_FRET_PER_FRET
    position_preference_bonus: float = POSITION_PREFERENCE_BONUS
    zone_preference_bonus: float = ZONE_PREFERENCE_BONUS


@dataclass(frozen=True)
class FingeringPreferences:
    """Lo que el usuario prefiere, serializable a JSON.

    positions: altura MIDI -> {"cuerda,traste": peso}. Peso en [0, 1] (se recorta); 1.0 es
        "siempre acá". El traste es relativo al capo, igual que la salida.
    zones: zona de la mano -> peso en [0, 1]. Zona = traste // ZONE_WIDTH (0 = trastes 0 a 3,
        1 = 4 a 7, ...). No cuenta para cuerdas al aire.

    JSON: {"positions": {"69": {"5,12": 0.8}}, "zones": {"1": 0.5}} (las claves son texto).
    """

    positions: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    zones: Mapping[int, float] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> "FingeringPreferences":
        data = data or {}
        positions = {
            int(midi): {_valid_key(key): float(w) for key, w in places.items()}
            for midi, places in (data.get("positions") or {}).items()
        }
        zones = {int(zone): float(w) for zone, w in (data.get("zones") or {}).items()}
        return cls(positions=positions, zones=zones)

    def to_json(self) -> dict[str, Any]:
        return {
            "positions": {
                str(midi): {key: _clamp01(w) for key, w in sorted(places.items())}
                for midi, places in sorted(self.positions.items())
            },
            "zones": {str(zone): _clamp01(w) for zone, w in sorted(self.zones.items())},
        }

    def position_weight(self, midi: int, string: int, fret: int) -> float:
        return _clamp01(self.positions.get(midi, {}).get(f"{string},{fret}", 0.0))

    def zone_weight(self, fret: int) -> float:
        return _clamp01(self.zones.get(fret // ZONE_WIDTH, 0.0))


def _valid_key(key: str) -> str:
    parts = str(key).split(",")
    if len(parts) != 2 or not all(part.strip().isdigit() for part in parts):
        raise ValueError(f'Clave de posición inválida {key!r}: se espera "cuerda,traste"')
    return f"{int(parts[0])},{int(parts[1])}"


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


@dataclass(frozen=True)
class FingeringStep:
    pitches: tuple[int, ...]  # alturas MIDI simultáneas (al menos una)
    time: float | None = None  # informativo: la digitación no lo usa
    duration: float | None = None


@dataclass(frozen=True)
class Placement:
    midi: int
    string: int  # 1 = la más aguda
    fret: int  # relativo al capo


@dataclass(frozen=True)
class _State:
    placements: tuple[Placement, ...]  # en el orden de las alturas del paso
    hand: int | None  # traste más bajo pisado; None si todo es al aire
    string_center: float
    cost: float  # costo propio del estado (sin transición)


def finger_steps(
    steps: Sequence[FingeringStep],
    *,
    tuning: Sequence[int] = STANDARD_TUNING,
    capo: int = 0,
    max_fret: int = DEFAULT_MAX_FRET,
    preferences: FingeringPreferences | None = None,
    costs: FingeringCosts | None = None,
) -> list[tuple[Placement, ...]]:
    """Digita cada paso; devuelve, por paso, un Placement por altura (en el mismo orden)."""
    prefs = preferences or FingeringPreferences()
    costs = costs or FingeringCosts()
    layers = [
        _states_for_step(i, step, tuning, capo, max_fret, prefs, costs)
        for i, step in enumerate(steps)
    ]
    return _viterbi(layers, costs)


def finger_notes(pitches: Sequence[int], **kwargs: Any) -> list[Placement]:
    """Atajo para una melodía: una nota por paso."""
    steps = [FingeringStep((p,)) for p in pitches]
    return [placements[0] for placements in finger_steps(steps, **kwargs)]


def _states_for_step(
    index: int,
    step: FingeringStep,
    tuning: Sequence[int],
    capo: int,
    max_fret: int,
    prefs: FingeringPreferences,
    costs: FingeringCosts,
) -> list[_State]:
    if not step.pitches:
        raise FingeringError(f"El paso {index} no tiene notas")
    if len(step.pitches) > len(tuning):
        raise FingeringError(
            f"El paso {index} tiene {len(step.pitches)} notas y la guitarra {len(tuning)} cuerdas"
        )
    options = [_note_options(p, index, tuning, capo, max_fret) for p in step.pitches]
    states: list[_State] = []
    _expand(options, [], set(), step.pitches, prefs, costs, states)
    if not states:
        raise FingeringError(
            f"El paso {index} {list(step.pitches)} no se puede tocar a la vez: las notas no "
            f"entran en {MAX_CHORD_SPAN} trastes en cuerdas distintas"
        )
    return _prune(states, MAX_STATES_PER_STEP)


def _prune(states: list[_State], limit: int) -> list[_State]:
    """Ordena por costo propio (estable) y, si hay que recortar, conserva el mejor estado de cada
    posición de mano antes de completar con los siguientes: no se pierde diversidad de mano."""
    ordered = sorted(states, key=lambda s: s.cost)
    if len(ordered) <= limit:
        return ordered
    best_per_hand: dict[int | None, _State] = {}
    for state in ordered:
        best_per_hand.setdefault(state.hand, state)
    kept = list(best_per_hand.values())[:limit]
    chosen = {id(s) for s in kept}
    kept += [s for s in ordered if id(s) not in chosen][: limit - len(kept)]
    return sorted(kept, key=lambda s: s.cost)


def _note_options(
    pitch: int, index: int, tuning: Sequence[int], capo: int, max_fret: int
) -> list[tuple[int, int]]:
    """(cuerda, traste relativo al capo) donde suena `pitch`, de la cuerda más aguda a la grave."""
    options = []
    for position in range(len(tuning) - 1, -1, -1):
        fret = pitch - tuning[position] - capo
        if 0 <= fret <= max_fret:
            options.append((len(tuning) - position, fret))
    if not options:
        raise UnplayableNoteError(pitch, index)
    return options


def _expand(
    options: list[list[tuple[int, int]]],
    chosen: list[tuple[int, int]],
    used: set[int],
    pitches: tuple[int, ...],
    prefs: FingeringPreferences,
    costs: FingeringCosts,
    out: list[_State],
) -> None:
    if len(chosen) == len(options):
        out.append(_build_state(pitches, chosen, prefs, costs))
        return
    for string, fret in options[len(chosen)]:
        if string in used:
            continue
        chosen.append((string, fret))
        if _span_ok(chosen):
            used.add(string)
            _expand(options, chosen, used, pitches, prefs, costs, out)
            used.discard(string)
        chosen.pop()


def _fretted(chosen: Sequence[tuple[int, int]]) -> list[int]:
    return [fret for _, fret in chosen if fret > 0]


def _span_ok(chosen: Sequence[tuple[int, int]]) -> bool:
    fretted = _fretted(chosen)
    return not fretted or max(fretted) - min(fretted) <= MAX_CHORD_SPAN


def _build_state(
    pitches: tuple[int, ...],
    chosen: Sequence[tuple[int, int]],
    prefs: FingeringPreferences,
    costs: FingeringCosts,
) -> _State:
    fretted = _fretted(chosen)
    cost = costs.chord_stretch_per_fret * (max(fretted) - min(fretted)) if fretted else 0.0
    for pitch, (string, fret) in zip(pitches, chosen, strict=True):
        cost += _note_cost(pitch, string, fret, prefs, costs)
    placements = tuple(Placement(p, s, f) for p, (s, f) in zip(pitches, chosen, strict=True))
    center = sum(s for s, _ in chosen) / len(chosen)
    return _State(placements, min(fretted) if fretted else None, center, cost)


def _note_cost(
    pitch: int, string: int, fret: int, prefs: FingeringPreferences, costs: FingeringCosts
) -> float:
    if fret == 0:
        cost = costs.open_string
        if pitch <= OPEN_LOW_REGISTER_MAX_MIDI:
            cost -= costs.open_low_register_bonus
    else:
        cost = costs.high_fret_per_fret * max(0, fret - costs.high_fret_start)
        cost -= costs.zone_preference_bonus * prefs.zone_weight(fret)
    return cost - costs.position_preference_bonus * prefs.position_weight(pitch, string, fret)


def _transition_cost(
    prev_hand: int | None, prev_center: float, cur: _State, costs: FingeringCosts
) -> float:
    cost = costs.string_change_per_string * abs(cur.string_center - prev_center)
    if prev_hand is not None and cur.hand is not None:
        shift = abs(cur.hand - prev_hand)
        cost += costs.hand_shift_per_fret * shift
        cost += costs.hand_shift_beyond_reach * max(0, shift - costs.hand_reach)
    return cost


def _viterbi(layers: list[list[_State]], costs: FingeringCosts) -> list[tuple[Placement, ...]]:
    """Cada estado lleva la posición de mano heredada del predecesor elegido: un paso todo al
    aire no la olvida."""
    if not layers:
        return []
    totals = [s.cost for s in layers[0]]
    hands = [s.hand for s in layers[0]]
    back: list[list[int]] = []
    for prev_layer, layer in zip(layers, layers[1:], strict=False):
        new_totals, new_hands, pointers = [], [], []
        for state in layer:
            best_index, best = 0, float("inf")
            for j, prev in enumerate(prev_layer):
                value = totals[j] + _transition_cost(hands[j], prev.string_center, state, costs)
                if value < best - _EPSILON:  # desempate estable: gana el primero
                    best_index, best = j, value
            new_totals.append(best + state.cost)
            new_hands.append(state.hand if state.hand is not None else hands[best_index])
            pointers.append(best_index)
        totals, hands = new_totals, new_hands
        back.append(pointers)
    index = min(range(len(totals)), key=lambda i: (totals[i], i))
    path = [index]
    for pointers in reversed(back):
        index = pointers[index]
        path.append(index)
    path.reverse()
    return [layers[i][k].placements for i, k in enumerate(path)]
