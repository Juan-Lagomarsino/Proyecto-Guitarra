import pytest

from guitarra_worker.domain.quantize import (
    GUITAR_MAX_MIDI,
    GUITAR_MIN_MIDI,
    BeatGrid,
    TimedNote,
    quantize_section,
)

STEADY = BeatGrid(beats_s=[i * 0.5 for i in range(40)], bpm=120.0)  # negras de 0,5 s


def note(onset, midi=60, offset=None, conf=0.9):
    return TimedNote(onset, onset + 0.1 if offset is None else offset, midi, conf)


def quantize(notes, start=0.0, end=8.0, grid=STEADY):
    return quantize_section(notes, start, end, grid)


def test_sixteenths_snap_to_nearest():
    events = quantize([note(0.0), note(0.13, 62), note(0.26, 64), note(0.37, 65)])
    assert [e.t for e in events] == pytest.approx([0.0, 0.25, 0.5, 0.75])


def test_triplets_win_when_error_is_lower():
    events = quantize([note(0.0), note(0.5 / 3, 62), note(1.0 / 3, 64)])
    assert [e.t for e in events] == pytest.approx([0.0, 1 / 3, 2 / 3], abs=1e-3)


def test_mixed_beats_choose_independently():
    events = quantize([note(0.0), note(0.125, 62), note(0.5), note(0.5 + 0.5 / 3, 62)])
    assert [e.t for e in events] == pytest.approx([0.0, 0.25, 1.0, 1 + 1 / 3], abs=1e-3)


def test_on_beat_notes_prefer_sixteenth_grid():
    events = quantize([note(0.01), note(0.5)])
    assert [e.t for e in events] == [0.0, 1.0]


def test_times_are_relative_to_section_start():
    events = quantize([note(2.0), note(2.5, 62)], start=2.0, end=4.0)
    assert [e.t for e in events] == pytest.approx([0.0, 1.0])


def test_note_at_section_end_is_excluded_and_at_start_included():
    events = quantize([note(2.0), note(4.0, 62)], start=2.0, end=4.0)
    assert [e.midi for e in events] == [60]


def test_note_snapping_to_section_end_is_dropped():
    assert quantize([note(3.99)], start=2.0, end=4.0) == []


def test_duration_runs_to_next_onset_without_overlap():
    events = quantize([note(0.0, 60, offset=5.0), note(0.5, 62), note(0.75, 64)])
    assert [e.t for e in events] == pytest.approx([0.0, 1.0, 1.5])
    # la última nota usa su largo observado
    assert [e.dur for e in events] == pytest.approx([1.0, 0.5, 0.25])


def test_same_pitch_never_overlaps():
    events = quantize([note(0.0, 60), note(0.12, 62), note(0.5, 60), note(0.62, 60)])
    by_pitch = [e for e in events if e.midi == 60]
    for a, b in zip(by_pitch, by_pitch[1:], strict=False):
        assert a.t + a.dur <= b.t + 1e-9


def test_simultaneous_notes_share_onset_and_duration():
    events = quantize([note(0.0, 40), note(0.0, 47), note(0.5, 52)])
    chord = [e for e in events if e.t == 0.0]
    assert sorted(e.midi for e in chord) == [40, 47]
    assert all(e.dur == pytest.approx(1.0) for e in chord)


def test_duplicate_pitch_on_same_slot_keeps_best_confidence():
    events = quantize([note(0.0, 60, conf=0.4), note(0.02, 60, conf=0.8)])
    assert len(events) == 1 and events[0].confidence == 0.8


def test_notes_outside_guitar_range_are_dropped():
    events = quantize([note(0.0, GUITAR_MIN_MIDI - 1), note(0.5, GUITAR_MAX_MIDI + 1), note(1.0)])
    assert [e.midi for e in events] == [60]


def test_range_limits_are_inclusive():
    events = quantize([note(0.0, GUITAR_MIN_MIDI), note(0.5, GUITAR_MAX_MIDI)])
    assert len(events) == 2


def test_confidence_is_kept_and_clamped():
    events = quantize([note(0.0, conf=0.55), note(0.5, 62, conf=1.7)])
    assert [e.confidence for e in events] == [0.55, 1.0]


def test_empty_section_gives_no_events():
    assert quantize([]) == []
    assert quantize([note(20.0)]) == []


def test_variable_tempo_grid():
    grid = BeatGrid(beats_s=[0.0, 0.5, 1.0, 2.0, 3.0, 4.0], bpm=90.0)
    events = quantize([note(1.0), note(1.5, 62), note(2.0, 64)], end=4.0, grid=grid)
    assert [e.t for e in events] == pytest.approx([2.0, 2.5, 3.0])


def test_without_grid_uses_bpm():
    events = quantize_section([note(0.0), note(0.5, 62)], 0.0, 4.0, BeatGrid(beats_s=[], bpm=120.0))
    assert [e.t for e in events] == pytest.approx([0.0, 1.0])


def test_single_beat_grid_falls_back_to_bpm():
    events = quantize_section([note(0.5)], 0.0, 4.0, BeatGrid(beats_s=[0.0], bpm=120.0))
    assert events[0].t == pytest.approx(1.0)


def test_no_grid_and_no_bpm_is_an_error():
    with pytest.raises(ValueError):
        quantize_section([note(0.0)], 0.0, 4.0, BeatGrid(beats_s=[], bpm=None))


def test_events_fit_inside_section():
    events = quantize([note(1.0, offset=9.0), note(1.5, 62, offset=9.0)], start=0.0, end=2.0)
    assert all(e.t + e.dur <= 4.0 + 1e-9 for e in events)


def test_note_too_close_to_section_end_is_dropped_not_zero_duration():
    # el ataque redondea a 3,99995 beats de una sección de 4: dur sería 0
    grid = BeatGrid(beats_s=[], bpm=120.0)
    events = quantize_section([note(1.999975)], 0.0, 2.0, grid)
    assert all(e.dur > 0 for e in events)
    assert events == []


def test_triplets_group_by_absolute_beat_when_section_starts_mid_beat():
    # la sección arranca en el beat 0,5; el tresillo está en los beats absolutos 1 + 0, 1/3, 2/3
    third = 0.5 / 3
    notes = [note(0.5), note(0.5 + third, 62), note(0.5 + 2 * third, 64)]
    events = quantize_section(notes, 0.25, 4.0, STEADY)
    assert [e.t for e in events] == pytest.approx([0.5, 0.5 + 1 / 3, 0.5 + 2 / 3], abs=1e-3)


@pytest.mark.parametrize(
    "grid",
    [
        STEADY,
        BeatGrid(beats_s=[0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0], bpm=90.0),
        BeatGrid(beats_s=[0.0, 0.4, 0.9, 1.5, 2.2, 3.0, 3.9], bpm=80.0),
        BeatGrid(beats_s=[], bpm=100.0),
    ],
)
def test_events_never_exceed_section_length_with_any_grid(grid):
    from guitarra_worker.domain.quantize import _beat_position

    start, end = 0.3, 3.0
    length = _beat_position(grid, end) - _beat_position(grid, start)
    notes = [note(start + i * 0.11, 55 + i % 7, offset=end + 5) for i in range(26)]
    events = quantize_section(notes, start, end, grid)
    assert events
    assert all(e.t >= 0 and e.dur > 0 and e.t + e.dur <= length + 1e-6 for e in events)
