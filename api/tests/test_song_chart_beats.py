"""Grilla de beats, rasgueo sin tiempo y conversión de segundos a beats."""

import pytest
from pydantic import ValidationError

from guitarra_api.domain.song_chart import SongChartContent, seconds_to_beats
from test_song_chart import A_MINOR, valid_chart, with_change, with_section

GRID = {"beats_s": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5], "downbeats_s": [0.0, 2.0]}


def test_chart_with_beat_grid_passes():
    SongChartContent.model_validate(with_change(beat_grid=GRID))


def test_chart_without_beat_grid_passes():
    assert SongChartContent.model_validate(valid_chart()).beat_grid is None


@pytest.mark.parametrize(
    "grid",
    [
        {"beats_s": [0.0, 0.5, 0.5, 1.0]},  # no creciente
        {"beats_s": [1.0, 0.5, 2.0]},
        {"beats_s": [0.5]},  # un solo beat
        {"beats_s": [-1.0, 0.0]},
        {"beats_s": [0.0, 0.5, 1.0], "downbeats_s": [0.25]},  # no es un beat
        {"beats_s": [0.0, 0.5, 1.0], "downbeats_s": [1.0, 0.0]},  # no creciente
        {"beats_s": [100.0, 100.5]},  # después del final de la canción
    ],
)
def test_invalid_beat_grid_is_rejected(grid):
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_change(beat_grid=grid))


def test_downbeats_match_beats_within_tolerance():
    grid = {"beats_s": [0.0, 0.5, 1.0], "downbeats_s": [0.005, 1.0]}
    SongChartContent.model_validate(with_change(beat_grid=grid))


def test_strum_has_no_time_and_accepts_beats_per_cycle():
    strum = {"pattern": "D-DU", "pattern_id": "a", "confidence": 0.5, "beats_per_cycle": 2}
    SongChartContent.model_validate(with_section(0, strum=strum))
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_section(0, strum={**strum, "t": 0}))


def test_strum_accent_outside_pattern_is_rejected():
    strum = {"pattern": "DU", "accent": [5], "pattern_id": "a", "confidence": 0.5}
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_section(0, strum=strum))


def test_chord_uses_t_s_not_t():
    chord = {"t": 1.0, "name": "Am", "shape": A_MINOR["shape"], "confidence": 0.5}
    with pytest.raises(ValidationError):
        SongChartContent.model_validate(with_section(0, chords=[chord]))


def grid(beats):
    return SongChartContent.model_validate(with_change(beat_grid={"beats_s": beats})).beat_grid


@pytest.mark.parametrize(
    ("t_s", "expected"),
    [(0.0, 0.0), (0.5, 1.0), (0.25, 0.5), (1.0, 2.0)],
)
def test_seconds_to_beats_on_constant_tempo(t_s, expected):
    assert seconds_to_beats(t_s, grid([0.0, 0.5, 1.0, 1.5])) == pytest.approx(expected)


def test_seconds_to_beats_follows_tempo_drift():
    drifting = grid([0.0, 0.5, 1.1, 1.8])
    assert seconds_to_beats(0.8, drifting) == pytest.approx(1.5)
    assert seconds_to_beats(1.1, drifting) == pytest.approx(2.0)


def test_seconds_to_beats_extrapolates_with_the_last_interval():
    beats = grid([0.0, 0.5, 1.1])
    assert seconds_to_beats(1.7, beats) == pytest.approx(3.0)
    assert seconds_to_beats(2.0, beats) == pytest.approx(2 + 0.9 / 0.6)


def test_seconds_to_beats_extrapolates_before_the_first_beat():
    assert seconds_to_beats(-0.25, grid([0.0, 0.5, 1.0])) == pytest.approx(-0.5)
