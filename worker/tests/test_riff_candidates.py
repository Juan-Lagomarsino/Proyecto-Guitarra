from guitarra_worker.domain.quantize import TimedNote
from guitarra_worker.domain.riff_candidates import (
    MIN_NOTES,
    SectionSpan,
    choose_candidates,
    mean_polyphony,
)


def line(start, count, step=0.25, midi=60):
    return [TimedNote(start + i * step, start + i * step + 0.1, midi, 0.9) for i in range(count)]


def chords(start, count, size=3, step=0.5):
    return [
        TimedNote(start + i * step, start + i * step + 0.4, 50 + 4 * k, 0.9)
        for i in range(count)
        for k in range(size)
    ]


def span(sid, start, end, name="Verso"):
    return SectionSpan(sid, name, start, end)


def test_mean_polyphony_single_line_is_one():
    assert mean_polyphony(line(0, 10)) == 1.0


def test_mean_polyphony_chords():
    assert mean_polyphony(chords(0, 6, size=3)) == 3.0


def test_mean_polyphony_empty_is_zero():
    assert mean_polyphony([]) == 0.0


def test_melodic_section_is_candidate():
    assert choose_candidates([span("verso-1", 0, 10)], line(1, MIN_NOTES)) == ["verso-1"]


def test_chordal_section_is_not_candidate():
    assert choose_candidates([span("estrofa", 0, 10)], chords(1, 10)) == []


def test_intro_is_candidate_even_if_polyphonic():
    sections = [span("intro-0", 0, 10, name="Intro")]
    assert choose_candidates(sections, chords(1, 10)) == ["intro-0"]


def test_too_few_notes_is_not_candidate_even_for_intro():
    sections = [span("intro-0", 0, 10, name="Intro")]
    assert choose_candidates(sections, line(1, MIN_NOTES - 1)) == []


def test_notes_are_assigned_by_onset_start_inclusive_end_exclusive():
    notes = line(5.0, MIN_NOTES)
    sections = [span("a", 0, 5.0), span("b", 5.0, 10)]
    assert choose_candidates(sections, notes) == ["b"]


def test_no_sections_or_notes():
    assert choose_candidates([], line(0, 10)) == []
    assert choose_candidates([span("a", 0, 5)], []) == []
