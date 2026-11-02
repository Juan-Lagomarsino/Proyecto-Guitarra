import json

from guitarra_core.fingering import STANDARD_TUNING, FingeringPreferences, finger_notes
from guitarra_core.fingering_preferences import LEARNING_RATE, learn_from_correction

EMPTY = FingeringPreferences()


def note(t, string, fret, **extra):
    return {"t": t, "string": string, "fret": fret, "dur": 0.25, **extra}


def learn(auto, user, *, capo=0, previous=EMPTY):
    return learn_from_correction(auto, user, tuning=STANDARD_TUNING, capo=capo, previous=previous)


def test_same_pitch_other_position_adds_preference():
    # La4 (69): cuerda 2 traste 10 -> cuerda 1 traste 5
    prefs = learn([note(0, 2, 10)], [note(0, 1, 5)])
    assert prefs.positions[69]["1,5"] == LEARNING_RATE
    assert prefs.zones[1] == LEARNING_RATE  # traste 5 -> zona 1


def test_rejected_position_goes_down():
    previous = FingeringPreferences(positions={69: {"2,10": 0.5}})
    prefs = learn([note(0, 2, 10)], [note(0, 1, 5)], previous=previous)
    assert prefs.positions[69]["2,10"] < 0.5


def test_previous_not_mutated():
    previous = FingeringPreferences(positions={69: {"1,5": 0.2}}, zones={1: 0.2})
    learn([note(0, 2, 10)], [note(0, 1, 5)], previous=previous)
    assert previous.to_json() == {"positions": {"69": {"1,5": 0.2}}, "zones": {"1": 0.2}}


def test_added_deleted_and_pitch_changed_do_not_count():
    auto = [note(1, 2, 10), note(2, 3, 7)]
    user = [note(2, 3, 9), note(3, 1, 3)]  # el de t=1 borrado, t=2 cambia de altura, t=3 agregado
    assert learn(auto, user).to_json() == EMPTY.to_json()


def test_return_to_automatic_adds_nothing():
    assert learn([note(0, 1, 5)], [note(0, 1, 5)]).to_json() == EMPTY.to_json()


def test_time_tolerance():
    assert 69 in learn([note(1.00, 2, 10)], [note(1.02, 1, 5)]).positions
    assert not learn([note(1.00, 2, 10)], [note(1.10, 1, 5)]).positions


def test_capo_respected():
    # capo 2: cuerda 1 traste 3 relativo = 64 + 2 + 3 = 69
    prefs = learn([note(0, 2, 8)], [note(0, 1, 3)], capo=2)
    assert prefs.positions[69] == {"1,3": LEARNING_RATE}


def test_open_string_choice_has_no_zone():
    # Mi4 (64): cuerda 2 traste 5 -> cuerda 1 al aire
    prefs = learn([note(0, 2, 5)], [note(0, 1, 0)])
    assert prefs.positions[64]["1,0"] == LEARNING_RATE
    assert not prefs.zones


def test_accumulation_is_bounded_and_grows():
    prefs = EMPTY
    previous_weight = 0.0
    for _ in range(30):
        prefs = learn([note(0, 2, 10)], [note(0, 1, 5)], previous=prefs)
        weight = prefs.positions[69]["1,5"]
        assert previous_weight < weight <= 1.0
        previous_weight = weight


def test_deterministic_stable_json():
    auto = [note(0, 2, 10), note(1, 3, 14)]
    user = [note(0, 1, 5), note(1, 2, 10)]
    a = json.dumps(learn(auto, user).to_json())
    b = json.dumps(learn(list(reversed(auto)), list(reversed(user))).to_json())
    assert a == b


def test_three_corrections_change_next_fingering():
    pitches = [69, 71, 69]
    first = finger_notes(pitches)[0]
    # una posición distinta de la automática para La4 (cuerda s: traste = 69 - afinación)
    alt = next(
        (s, 69 - STANDARD_TUNING[6 - s])
        for s in range(1, 7)
        if (s, 69 - STANDARD_TUNING[6 - s]) != (first.string, first.fret)
        and 0 <= 69 - STANDARD_TUNING[6 - s] <= 12
    )
    assert alt != (first.string, first.fret)
    prefs = EMPTY
    for _ in range(3):
        prefs = learn([note(0, first.string, first.fret)], [note(0, *alt)], previous=prefs)
    after = finger_notes(pitches, preferences=prefs)
    assert (after[0].string, after[0].fret) == alt
    assert (after[2].string, after[2].fret) == alt


def test_tiny_weights_are_pruned():
    previous = FingeringPreferences(positions={69: {"2,10": 0.06}}, zones={3: 0.04})
    prefs = learn([note(0, 2, 10)], [note(0, 1, 5)], previous=previous)
    assert "2,10" not in prefs.positions[69]
    assert 3 not in prefs.zones


def test_unison_in_reversed_order_learns_nothing():
    # Mi4 (64) a la vez en (2,5) y (1,0)
    auto = [note(0, 2, 5), note(0, 1, 0)]
    assert learn(auto, list(reversed(auto))).to_json() == EMPTY.to_json()


def test_octaves_do_not_cross():
    auto = [note(0, 6, 0), note(0, 4, 2)]  # Mi2 y Mi3
    assert learn(auto, list(reversed(auto))).to_json() == EMPTY.to_json()


def test_unison_with_one_changed_learns_only_that_one():
    auto = [note(0, 2, 5), note(0, 1, 0)]
    user = [note(0, 1, 0), note(0, 3, 9)]  # Mi4 en (3,9) en lugar de (2,5)
    prefs = learn(auto, user)
    assert prefs.positions[64] == {"3,9": LEARNING_RATE}


def test_repeatedly_rejected_position_is_pruned():
    prefs = FingeringPreferences(positions={69: {"2,10": 0.5}})
    for _ in range(10):
        prefs = learn([note(0, 2, 10)], [note(0, 1, 5)], previous=prefs)
    assert "2,10" not in prefs.positions[69]
