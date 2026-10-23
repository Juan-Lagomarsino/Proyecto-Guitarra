import pytest

from guitarra_core.chord_shapes import (
    CURATED_SHAPES,
    lowest_pitch_class,
    shape_pitch_classes,
    shapes_for,
)
from guitarra_core.theory import NOTE_NAMES, parse_chord, parse_note, pitch_classes

ROOTS = NOTE_NAMES
KINDS = {"open", "barre", "power", "movable"}


def sounded(shape) -> frozenset[int]:
    return shape_pitch_classes(shape.shape)


def assert_plays_exactly(shape):
    expected = pitch_classes(parse_chord(shape.chord))
    assert sounded(shape) == expected, f"{shape.chord} {shape.shape}"


def assert_well_formed(shape):
    assert len(shape.shape) == 6
    assert len(shape.fingers) == 6
    assert shape.kind in KINDS
    assert shape.difficulty > 0
    assert all(f == "x" or 0 <= f <= 24 for f in shape.shape)
    if shape.barre:
        assert shape.barre.from_string > shape.barre.to_string
        assert shape.barre.fret >= 1


@pytest.mark.parametrize("name", sorted(CURATED_SHAPES))
def test_curated_shapes_play_exact_notes(name):
    shapes = [s for s in shapes_for(name) if s.kind == "open"]
    assert shapes, name
    for shape in shapes:
        assert shape.chord == name
        assert_plays_exactly(shape)
        assert_well_formed(shape)


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize("suffix", ["", "m", "7", "m7", "maj7"])
def test_generated_shapes_play_exact_notes(root, suffix):
    shapes = shapes_for(root + suffix)
    assert shapes
    for shape in shapes:
        assert shape.fallback is None
        assert shape.name == root + suffix
        assert_plays_exactly(shape)
        assert_well_formed(shape)


@pytest.mark.parametrize("root", ROOTS)
@pytest.mark.parametrize(
    "suffix", ["sus2", "sus4", "6", "9", "aug", "dim", "dim7", "m7b5", "add9", "7sus4"]
)
def test_other_qualities_play_exact_notes(root, suffix):
    for shape in shapes_for(root + suffix):
        assert_plays_exactly(shape)
        assert_well_formed(shape)


def test_every_movable_root_has_a_barre_option_for_major():
    for root in ROOTS:
        kinds = {s.kind for s in shapes_for(root)}
        assert kinds & {"open", "barre"}


def test_f_major_is_a_barre_chord():
    shape = next(s for s in shapes_for("F") if s.shape == (1, 3, 3, 2, 1, 1))
    assert shape.kind == "barre"
    assert shape.barre.fret == 1
    assert (shape.barre.from_string, shape.barre.to_string) == (6, 1)


def test_open_c_is_the_easiest_c():
    best = min(shapes_for("C"), key=lambda s: s.difficulty)
    assert best.shape == ("x", 3, 2, 0, 1, 0)
    assert best.kind == "open"
    assert best.barre is None
    assert best.fingers == (0, 3, 2, 0, 1, 0)


def test_power_chords_in_dictionary():
    shapes = shapes_for("C5")
    assert {s.kind for s in shapes} == {"power"}
    assert any(s.shape == ("x", 3, 5, 5, "x", "x") for s in shapes)
    assert any(s.shape == (8, 10, 10, "x", "x", "x") for s in shapes)
    for shape in shapes:
        assert_plays_exactly(shape)


@pytest.mark.parametrize("name", ["C/G", "Am/E", "D/F#", "G/B", "C/E", "F/C", "Bm/F#", "Bb/D"])
def test_slash_chords_have_bass_as_lowest_note(name):
    chord = parse_chord(name)
    shapes = shapes_for(name)
    assert shapes
    for shape in shapes:
        assert shape.fallback is None
        assert shape.chord == chord.name
        assert lowest_pitch_class(shape.shape) == parse_note(chord.bass)
        assert_plays_exactly(shape)
        assert_well_formed(shape)


def test_slash_chord_with_foreign_bass_never_breaks():
    shapes = shapes_for("C/D")
    assert shapes
    for shape in shapes:
        assert_plays_exactly(shape)
        if shape.fallback is None:
            assert lowest_pitch_class(shape.shape) == 2


def test_slash_chord_falls_back_to_chord_without_bass_when_impossible():
    # Bajo imposible de agregar a cualquier forma: se cae al acorde sin bajo, con marca.
    shapes = shapes_for("C5/F#")
    assert shapes
    for shape in shapes:
        assert shape.name == "C5/F#"
        if shape.fallback:
            assert shape.fallback == "sin_bajo"
            assert shape.chord == "C5"
        assert_plays_exactly(shape)


def test_unknown_extension_falls_back_to_simpler_chord():
    shapes = shapes_for("Cmaj9")
    assert shapes
    for shape in shapes:
        assert shape.name == "Cmaj9"
        assert_plays_exactly(shape)
    assert all(s.fallback in (None, "simplificado") for s in shapes)


def test_chord_without_forms_has_simplified_fallback():
    shapes = shapes_for("Cm9")
    assert shapes
    assert all(s.fallback == "simplificado" for s in shapes)
    assert {s.chord for s in shapes} == {"Cm7"}


def test_slash_chord_with_impossible_bass_keeps_chord_without_bass():
    shapes = shapes_for("Em7b5/Bb")
    assert shapes
    assert all(s.chord.startswith("Em7b5") for s in shapes)


@pytest.mark.parametrize("name", ["C13", "Cfoo", "Dm7b9", "C11"])
def test_unparseable_names_fall_back_without_breaking(name):
    shapes = shapes_for(name)
    assert shapes
    for shape in shapes:
        assert shape.fallback == "simplificado"
        assert_plays_exactly(shape)


@pytest.mark.parametrize("name", ["N", "", "???", "H7"])
def test_no_chord_or_garbage_returns_empty(name):
    assert shapes_for(name) == ()


def test_aliases_resolve_to_same_shapes():
    assert [s.shape for s in shapes_for("A:min")] == [s.shape for s in shapes_for("Am")]


def test_to_notation_has_chord_model_fields():
    shape = next(s for s in shapes_for("F") if s.shape == (1, 3, 3, 2, 1, 1))
    data = shape.to_notation()
    assert data["shape"] == [1, 3, 3, 2, 1, 1]
    assert data["barre"] == {"fret": 1, "from_string": 6, "to_string": 1}
    open_c = min(shapes_for("C"), key=lambda s: s.difficulty).to_notation()
    assert open_c["barre"] is None
    assert open_c["shape"] == ["x", 3, 2, 0, 1, 0]
