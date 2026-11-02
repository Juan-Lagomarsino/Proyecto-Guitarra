"""Aprender preferencias de digitación de un par (riff automático, riff corregido). Puro: sin I/O.

Solo cuenta como preferencia cuando la MISMA altura, en el mismo momento, cambió de cuerda o
traste. Notas agregadas, borradas o con la altura cambiada no son preferencias de digitación.

Los eventos son dicts del formato de notación: `t` (beats relativos a la sección), `string`
(1 = la más aguda) y `fret` (relativo al capo). La afinación va de grave a aguda, en MIDI.

Acumulación: media móvil exponencial hacia 1. Peso nuevo = viejo + ALPHA * (1 - viejo): una
corrección sola no domina (0.3) y tres iguales sí (~0.66).
"""

from collections.abc import Mapping, Sequence
from typing import Any

from guitarra_core.fingering import ZONE_WIDTH, FingeringPreferences

LEARNING_RATE = 0.3  # alfa de la media móvil exponencial
REJECTION_DECAY = 0.3  # la posición automática rechazada pierde esta fracción de su peso
MATCH_TOLERANCE_BEATS = 1 / 32  # diferencia máxima de `t` (beats) para emparejar la misma nota
MIN_WEIGHT = 0.05  # los pesos menores se podan para no dejar residuos

Event = Mapping[str, Any]
_Position = tuple[int, int]  # (cuerda, traste)


def learn_from_correction(
    auto_events: Sequence[Event],
    user_events: Sequence[Event],
    *,
    tuning: Sequence[int],
    capo: int,
    previous: FingeringPreferences,
) -> FingeringPreferences:
    """Devuelve las preferencias actualizadas; `previous` no se modifica."""
    positions = {midi: dict(places) for midi, places in previous.positions.items()}
    zones = dict(previous.zones)
    for pitch, rejected, chosen in _changed_fingerings(auto_events, user_events, tuning, capo):
        places = positions.setdefault(pitch, {})
        rejected_key, chosen_key = _key(rejected), _key(chosen)
        if rejected_key in places:
            places[rejected_key] *= 1 - REJECTION_DECAY
        places[chosen_key] = _reinforce(places.get(chosen_key, 0.0))
        if chosen[1] > 0:  # una cuerda al aire no cuenta como zona de mano
            zone = chosen[1] // ZONE_WIDTH
            zones[zone] = _reinforce(zones.get(zone, 0.0))
    return _pruned(positions, zones)


def _reinforce(weight: float) -> float:
    return weight + LEARNING_RATE * (1.0 - weight)


def _key(position: _Position) -> str:
    return f"{position[0]},{position[1]}"


def _pitch(event: Event, tuning: Sequence[int], capo: int) -> int:
    return tuning[len(tuning) - int(event["string"])] + capo + int(event["fret"])


def _position(event: Event) -> _Position:
    return int(event["string"]), int(event["fret"])


def _changed_fingerings(
    auto_events: Sequence[Event], user_events: Sequence[Event], tuning: Sequence[int], capo: int
) -> list[tuple[int, _Position, _Position]]:
    """(altura, posición automática, posición del usuario) de los pares emparejados que difieren."""
    remaining = sorted(user_events, key=_order)
    autos = sorted(auto_events, key=_order)
    # Primero las idénticas (misma cuerda, traste y tiempo): así un unísono no se cruza.
    unmatched = [a for a in autos if not _take_match(remaining, a, tuning, capo, same_place=True)]
    changes = []
    for auto in unmatched:
        match = _take_match(remaining, auto, tuning, capo, same_place=False)
        if match is not None:
            changes.append((_pitch(auto, tuning, capo), _position(auto), _position(match)))
    return changes


def _order(event: Event) -> tuple[float, int, int]:
    return float(event["t"]), int(event["string"]), int(event["fret"])


def _take_match(
    remaining: list[Event], auto: Event, tuning: Sequence[int], capo: int, *, same_place: bool
) -> Event | None:
    """Saca de `remaining` la nota del usuario de la misma altura más cercana en el tiempo (dentro
    de la tolerancia; el primero gana el empate). Con `same_place` exige misma cuerda y traste.
    Cada nota del usuario se empareja una sola vez."""
    pitch, time = _pitch(auto, tuning, capo), float(auto["t"])
    best_index, best_gap = None, MATCH_TOLERANCE_BEATS
    for i, event in enumerate(remaining):
        gap = abs(float(event["t"]) - time)
        if gap > best_gap or _pitch(event, tuning, capo) != pitch:
            continue
        if same_place and _position(event) != _position(auto):
            continue
        if best_index is None or gap < best_gap:
            best_index, best_gap = i, gap
    return None if best_index is None else remaining.pop(best_index)


def _pruned(
    positions: Mapping[int, Mapping[str, float]], zones: Mapping[int, float]
) -> FingeringPreferences:
    kept = {
        midi: {key: w for key, w in places.items() if w >= MIN_WEIGHT}
        for midi, places in positions.items()
    }
    return FingeringPreferences(
        positions={midi: places for midi, places in kept.items() if places},
        zones={zone: w for zone, w in zones.items() if w >= MIN_WEIGHT},
    )
