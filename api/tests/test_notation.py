import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from guitarra_api.domain.notation import Notation, build_json_schema

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "notation.schema.json"

PLAN_EXAMPLE = {
    "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
    "bpm": 90,
    "time_signature": "4/4",
    "events": [
        {"t": 0.0, "dur": 0.5, "string": 6, "fret": 5, "technique": None},
        {"t": 0.5, "dur": 0.5, "string": 6, "fret": 7, "technique": "h"},
        {"t": 1.0, "dur": 1.0, "string": 5, "fret": 7, "technique": "b", "bend": 1},
    ],
    "chords": [{"t": 0, "name": "Am", "shape": ["x", 0, 2, 2, 1, 0], "barre": None}],
    "strum": [{"t": 0, "pattern": "D-DU-UDU", "accent": [0, 4]}],
    "tonic": "A",
}


def with_change(**changes):
    data = copy.deepcopy(PLAN_EXAMPLE)
    data.update(changes)
    return data


def with_event(**changes):
    event = {"t": 0, "dur": 1, "string": 1, "fret": 0, "technique": None, **changes}
    return with_change(events=[event])


def test_plan_example_validates_as_is():
    notation = Notation.model_validate(PLAN_EXAMPLE)
    assert notation.bpm == 90
    assert notation.events[2].bend == 1


def test_minimal_notation_uses_defaults():
    notation = Notation.model_validate({"bpm": 120})
    assert notation.tuning == ["E2", "A2", "D3", "G3", "B3", "E4"]
    assert notation.time_signature == "4/4"
    assert notation.events == []
    assert notation.chords == []
    assert notation.strum == []
    assert notation.tonic is None


def test_bpm_is_required():
    with pytest.raises(ValidationError):
        Notation.model_validate({})


def test_round_trip_keeps_plan_fields():
    dumped = Notation.model_validate(PLAN_EXAMPLE).model_dump(mode="json")
    assert dumped["events"][0]["technique"] is None
    assert dumped["chords"][0]["shape"] == ["x", 0, 2, 2, 1, 0]
    assert dumped["chords"][0]["barre"] is None


@pytest.mark.parametrize("technique", ["h", "p", "/", "\\", "b", "r", "~", "pm", "x", None])
def test_valid_techniques(technique):
    extra = {"bend": 0.5} if technique == "b" else {}
    Notation.model_validate(with_event(technique=technique, **extra))


def test_technique_defaults_to_none_when_missing():
    data = with_change(events=[{"t": 0, "dur": 1, "string": 1, "fret": 0}])
    assert Notation.model_validate(data).events[0].technique is None


@pytest.mark.parametrize(
    "changes",
    [
        {"string": 0},
        {"string": 7},
        {"fret": -1},
        {"fret": 25},
        {"technique": "zz"},
        {"technique": "b"},  # bend sin valor
        {"technique": "h", "bend": 1},  # bend sin técnica b
        {"technique": None, "bend": 1},
        {"technique": "b", "bend": 0},
        {"t": -0.5},
        {"dur": -1},
        {"dur": 0},
    ],
)
def test_invalid_events(changes):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_event(**changes))


@pytest.mark.parametrize(
    "tuning",
    [
        ["E2", "A2", "D3", "G3", "B3"],
        ["E2", "A2", "D3", "G3", "B3", "E4", "A4"],
        ["E", "A2", "D3", "G3", "B3", "E4"],  # sin octava
        ["H2", "A2", "D3", "G3", "B3", "E4"],
    ],
)
def test_invalid_tuning(tuning):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(tuning=tuning))


def test_tuning_accepts_accidentals():
    Notation.model_validate(with_change(tuning=["D#2", "Ab2", "Db3", "F#3", "Bb3", "D#4"]))


@pytest.mark.parametrize("tonic", ["A", "C#", "Bb", "G", None])
def test_valid_tonic(tonic):
    Notation.model_validate(with_change(tonic=tonic))


@pytest.mark.parametrize("tonic", ["H", "A2", "c", "", "A##", "Am"])
def test_invalid_tonic(tonic):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(tonic=tonic))


@pytest.mark.parametrize(
    "shape",
    [
        ["x", 0, 2, 2, 1],
        ["x", 0, 2, 2, 1, 0, 0],
        ["x", 0, 2, 2, 1, 25],
        ["x", 0, 2, 2, 1, -1],
        ["y", 0, 2, 2, 1, 0],
    ],
)
def test_invalid_chord_shape(shape):
    chord = {"t": 0, "name": "Am", "shape": shape, "barre": None}
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(chords=[chord]))


def test_chord_with_barre():
    chord = {
        "t": 0,
        "name": "F",
        "shape": [1, 3, 3, 2, 1, 1],
        "barre": {"fret": 1, "from_string": 6, "to_string": 1},
    }
    notation = Notation.model_validate(with_change(chords=[chord]))
    assert notation.chords[0].barre.fret == 1


@pytest.mark.parametrize(
    "barre",
    [
        {"fret": 0, "from_string": 6, "to_string": 1},
        {"fret": 1, "from_string": 7, "to_string": 1},
        {"fret": 1, "from_string": 3, "to_string": 3},
        {"fret": 1, "from_string": 2, "to_string": 5},
        {"fret": 1, "from_string": 6},
    ],
)
def test_invalid_barre(barre):
    chord = {"t": 0, "name": "F", "shape": [1, 3, 3, 2, 1, 1], "barre": barre}
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(chords=[chord]))


def test_negative_chord_time_is_invalid():
    chord = {"t": -1, "name": "Am", "shape": ["x", 0, 2, 2, 1, 0], "barre": None}
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(chords=[chord]))


@pytest.mark.parametrize(
    "strum",
    [
        {"t": -1, "pattern": "DU", "accent": []},
        {"t": 0, "pattern": "", "accent": []},
        {"t": 0, "pattern": "DZ", "accent": []},
        {"t": 0, "pattern": "DU", "accent": [2]},
        {"t": 0, "pattern": "DU", "accent": [-1]},
    ],
)
def test_invalid_strum(strum):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(strum=[strum]))


@pytest.mark.parametrize("changes", [{"bpm": 0}, {"bpm": -10}, {"time_signature": "cuatro"}])
def test_invalid_top_level(changes):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(**changes))


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        Notation.model_validate(with_change(volumen=11))


def test_committed_json_schema_matches_model():
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == build_json_schema(), (
        "schemas/notation.schema.json está viejo: correr "
        "`python api/scripts/export_notation_schema.py`"
    )


@pytest.mark.parametrize("confidence", [0, 0.5, 1])
def test_event_confidence_in_range_is_accepted(confidence):
    notation = Notation.model_validate(with_event(confidence=confidence))
    assert notation.events[0].confidence == confidence


def test_event_confidence_is_optional():
    assert Notation.model_validate(with_event()).events[0].confidence is None


@pytest.mark.parametrize("confidence", [-0.1, 1.01])
def test_event_confidence_out_of_range_is_rejected(confidence):
    with pytest.raises(ValidationError):
        Notation.model_validate(with_event(confidence=confidence))
