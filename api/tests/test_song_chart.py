import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from guitarra_api.domain.song_chart import (
    SongChartContent,
    build_json_schema,
    overall_confidence,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "song_chart.schema.json"

A_MINOR = {"t_s": 1.0, "name": "Am", "shape": ["x", 0, 2, 2, 1, 0], "confidence": 0.9}
C_MAJOR = {"t_s": 5.0, "name": "C", "shape": ["x", 3, 2, 0, 1, 0], "confidence": 0.8}


def valid_chart() -> dict:
    return {
        "instrument": "electric",
        "key": {"tonic": "A", "mode": "minor", "confidence": 0.7},
        "bpm": 96,
        "bpm_confidence": 0.95,
        "time_signature": "4/4",
        "capo": 0,
        "sections": [
            {
                "id": "intro",
                "name": "Intro",
                "start_s": 0,
                "end_s": 10,
                "order": 0,
                "chord_source": "detected",
                "chords": [A_MINOR, C_MAJOR],
                "strum": {
                    "pattern": "D-DU-UDU",
                    "pattern_id": "folk-8",
                    "confidence": 0.6,
                },
            },
            {
                "id": "verse-1",
                "name": "Estrofa",
                "start_s": 10,
                "end_s": 30,
                "order": 1,
                "chord_source": "cifraclub",
                "chords": [{**A_MINOR, "t_s": 10.0}],
            },
        ],
        "sources": [{"step": "chords", "tool": "chordino", "version": "1.0"}],
    }


def with_change(**changes) -> dict:
    return {**valid_chart(), **changes}


def with_section(index: int, **changes) -> dict:
    chart = copy.deepcopy(valid_chart())
    chart["sections"][index].update(changes)
    return chart


def test_valid_chart_passes():
    chart = SongChartContent.model_validate(valid_chart())
    assert chart.sections[0].chords[0].name == "Am"


def test_minimal_chart_passes():
    section = {
        "id": "a",
        "name": "A",
        "start_s": 0,
        "end_s": 1,
        "order": 0,
        "chord_source": "user",
    }
    chart = SongChartContent.model_validate(
        {"instrument": "classical", "bpm": 60, "sections": [section]}
    )
    assert chart.capo == 0 and chart.sources == []


def test_classical_chart_accepts_arpeggio():
    chart = with_section(
        0, arpeggio={"pattern_id": "pima-6", "pattern": "p-i-m-a-m-i", "confidence": 0.5}
    )
    chart["instrument"] = "classical"
    SongChartContent.model_validate(chart)


@pytest.mark.parametrize(
    "changes",
    [
        {"instrument": "bass"},
        {"bpm": 0},
        {"bpm": -3},
        {"capo": -1},
        {"capo": 13},
        {"sections": []},
        {"time_signature": "cuatro"},
        {"volumen": 11},
        {"key": {"tonic": "H", "mode": "minor", "confidence": 0.5}},
        {"key": {"tonic": "A", "mode": "dorian", "confidence": 0.5}},
        {"bpm_confidence": 1.2},
        {"sources": [{"step": "chords", "tool": "chordino"}]},
    ],
)
def test_invalid_chart_level_fields_are_rejected(changes):
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_change(**changes))


@pytest.mark.parametrize("capo", [0, 12])
def test_capo_limits_are_accepted(capo):
    SongChartContent.model_validate(with_change(capo=capo))


@pytest.mark.parametrize(
    "changes",
    [
        {"start_s": 10, "end_s": 10},
        {"start_s": 12, "end_s": 5},
        {"id": "Intro Uno"},
        {"name": ""},
        {"chord_source": "magia"},
        {"chords": [{**A_MINOR, "t_s": 10.0}]},  # justo en el fin: fuera
        {"chords": [{**A_MINOR, "t_s": 12.0}]},
        {"chords": [C_MAJOR, A_MINOR]},  # desordenados
        {"chords": [{**A_MINOR, "confidence": 1.1}]},
        {"chords": [{**A_MINOR, "confidence": -0.1}]},
        {"chords": [{"t_s": 1.0, "name": "Am", "shape": ["x", 0, 2], "confidence": 0.5}]},
        {"chords": [{"t_s": 1.0, "name": "Am", "shape": A_MINOR["shape"]}]},  # sin confidence
        {"strum": {"pattern": "XYZ", "pattern_id": "a", "confidence": 0.5}},
        {"strum": {"pattern": "DU", "confidence": 0.5}},  # sin pattern_id
        {"strum": {"pattern": "DU", "pattern_id": "a", "confidence": 2}},
    ],
)
def test_invalid_section_fields_are_rejected(changes):
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_section(0, **changes))


def test_overlapping_sections_are_rejected():
    with pytest.raises(ValidationError, match="solapan"):
        SongChartContent.model_validate(with_section(1, start_s=9, chords=[]))


def test_sections_out_of_time_order_are_rejected():
    chart = valid_chart()
    chart["sections"].reverse()
    chart["sections"][0]["order"], chart["sections"][1]["order"] = 0, 1
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(chart)


def test_repeated_section_ids_are_rejected():
    with pytest.raises(ValidationError, match="únicos"):
        SongChartContent.model_validate(with_section(1, id="intro"))


def test_non_increasing_order_is_rejected():
    with pytest.raises(ValidationError, match="order"):
        SongChartContent.model_validate(with_section(1, order=0))


def test_arpeggio_in_electric_chart_is_rejected():
    arpeggio = {"pattern_id": "pima-6", "pattern": "p-i-m-a", "confidence": 0.5}
    with pytest.raises(ValidationError, match="clásica"):
        SongChartContent.model_validate(with_section(0, arpeggio=arpeggio))


def test_arpeggio_pattern_must_use_pima_fingers():
    chart = with_section(0, arpeggio={"pattern_id": "x", "pattern": "p-z", "confidence": 0.5})
    chart["instrument"] = "classical"
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(chart)


def test_overall_confidence_averages_every_confidence():
    chart = SongChartContent.model_validate(valid_chart())
    # key .7, bpm .95, acordes .9 .8 .9, rasgueo .6
    assert overall_confidence(chart) == pytest.approx((0.7 + 0.95 + 0.9 + 0.8 + 0.9 + 0.6) / 6)


def test_overall_confidence_is_none_without_data():
    section = {
        "id": "a",
        "name": "A",
        "start_s": 0,
        "end_s": 1,
        "order": 0,
        "chord_source": "user",
    }
    chart = SongChartContent.model_validate(
        {"instrument": "electric", "bpm": 90, "sections": [section]}
    )
    assert overall_confidence(chart) is None


def test_committed_json_schema_matches_model():
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == build_json_schema(), (
        "schemas/song_chart.schema.json está viejo: correr "
        "`python api/scripts/export_song_chart_schema.py`"
    )


def riff(*events: dict, **changes) -> dict:
    return {"bpm": 96, "events": list(events), **changes}


def note(t: float, dur: float = 1.0, **changes) -> dict:
    return {"t": t, "dur": dur, "string": 6, "fret": 3, **changes}


def test_chart_without_riff_still_validates():
    chart = SongChartContent.model_validate(valid_chart())
    assert all(section.riff is None for section in chart.sections)


def test_riff_inside_the_section_is_accepted_with_standard_tuning():
    # sección de 10 s a 96 bpm = 16 beats
    chart = SongChartContent.model_validate(
        with_section(0, riff=riff(note(0, confidence=0.7), note(15, 1)))
    )
    riff_notation = chart.sections[0].riff
    assert riff_notation is not None
    assert riff_notation.tuning == ["E2", "A2", "D3", "G3", "B3", "E4"]
    assert riff_notation.events[0].confidence == 0.7


def test_riff_that_runs_past_the_section_is_rejected_by_bpm():
    with pytest.raises(ValidationError, match="riff"):
        SongChartContent.model_validate(with_section(0, riff=riff(note(15.5, 1))))


def test_riff_length_uses_the_beat_grid_when_present():
    grid = {"beats_s": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], "downbeats_s": [0.0]}
    chart = {**valid_chart(), "beat_grid": grid}
    chart["sections"][0].update(end_s=4.0, chords=[A_MINOR], riff=riff(note(3, 1)))
    chart["sections"][1].update(start_s=4.0, chords=[{**A_MINOR, "t_s": 4.0}])
    SongChartContent.model_validate(chart)  # 4 beats exactos
    chart["sections"][0]["riff"] = riff(note(3.5, 1))
    with pytest.raises(ValidationError, match="riff"):
        SongChartContent.model_validate(chart)


def test_riff_beats_are_relative_to_the_section_start():
    chart = {**valid_chart(), "beat_grid": {"beats_s": [float(s) for s in range(0, 31)]}}
    # sección 2: 10 s a 30 s = 20 beats desde su inicio
    chart["sections"][1]["riff"] = riff(note(19, 1))
    SongChartContent.model_validate(chart)
    chart["sections"][1]["riff"] = riff(note(19.5, 1))
    with pytest.raises(ValidationError, match="riff"):
        SongChartContent.model_validate(chart)


def test_empty_riff_is_rejected():
    with pytest.raises(ValidationError, match="eventos"):
        SongChartContent.model_validate(with_section(0, riff=riff()))


def test_riff_event_confidence_out_of_range_is_rejected():
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_section(0, riff=riff(note(0, confidence=1.5))))
