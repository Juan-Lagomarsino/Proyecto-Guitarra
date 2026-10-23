import pytest

from guitarra_core.theory import (
    ChordParseError,
    note_name,
    parse_chord,
    parse_note,
    pitch_classes,
    transpose_chord,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("C", "C"),
        ("Cm", "Cm"),
        ("C7", "C7"),
        ("Cmaj7", "Cmaj7"),
        ("Cm7", "Cm7"),
        ("Cdim", "Cdim"),
        ("Caug", "Caug"),
        ("Csus2", "Csus2"),
        ("Csus4", "Csus4"),
        ("Cadd9", "Cadd9"),
        ("C6", "C6"),
        ("C9", "C9"),
        ("C5", "C5"),
        ("C/G", "C/G"),
        ("Am/E", "Am/E"),
        ("A:min", "Am"),
        ("A:maj", "A"),
        ("A#", "Bb"),
        ("Bb", "Bb"),
        ("C#m", "Dbm"),
        ("C7M", "Cmaj7"),
        ("CM7", "Cmaj7"),
        ("Cº", "Cdim"),
        ("C°", "Cdim"),
        ("C°7", "Cdim7"),
        ("C(9)", "Cadd9"),
        ("C7(9)", "C9"),
        ("Em7(b5)", "Em7b5"),
        ("Cmin7", "Cm7"),
        ("C-7", "Cm7"),
        ("C+", "Caug"),
        ("C:hdim7", "Cm7b5"),
        ("D:7", "D7"),
        ("G:min7", "Gm7"),
        ("C:maj/5", "C/G"),
        ("Cmaj9", "Cmaj9"),
        ("Cm9", "Cm9"),
        ("C7sus4", "C7sus4"),
        ("Bbm/Db", "Bbm/Db"),
        ("C/D", "C/D"),
    ],
)
def test_parse_and_canonical_name(text, expected):
    assert parse_chord(text).name == expected


def test_no_chord_returns_none():
    assert parse_chord("N") is None
    assert parse_chord("N.C.") is None


def test_parsed_fields():
    chord = parse_chord("Am/E")
    assert (chord.root, chord.quality, chord.extensions, chord.bass) == ("A", "min", (), "E")
    chord = parse_chord("Em7(b5)")
    assert chord.quality == "min"
    assert chord.extensions == ("7", "b5")
    assert parse_chord("C5").quality == "power"


@pytest.mark.parametrize("text", ["", "H", "Cfoo", "C13", "H7", "/G", "C/"])
def test_invalid_names(text):
    with pytest.raises(ChordParseError):
        parse_chord(text)


def test_note_enharmony():
    assert parse_note("A#") == parse_note("Bb") == 10
    assert parse_note("E#") == 5
    assert parse_note("Cb") == 11
    assert note_name(1) == "Db"
    assert note_name(13) == "Db"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("C", {0, 4, 7}),
        ("Cm", {0, 3, 7}),
        ("C7", {0, 4, 7, 10}),
        ("Cmaj7", {0, 4, 7, 11}),
        ("Cdim", {0, 3, 6}),
        ("Cdim7", {0, 3, 6, 9}),
        ("Em7b5", {4, 7, 10, 2}),
        ("C9", {0, 4, 7, 10, 2}),
        ("Cadd9", {0, 4, 7, 2}),
        ("C5", {0, 7}),
        ("C6", {0, 4, 7, 9}),
        ("Csus2", {0, 2, 7}),
        ("C/D", {0, 4, 7, 2}),
        ("C/G", {0, 4, 7}),
    ],
)
def test_pitch_classes(name, expected):
    assert pitch_classes(parse_chord(name)) == frozenset(expected)


def test_transpose():
    assert transpose_chord(parse_chord("Bm"), -2).name == "Am"
    assert transpose_chord(parse_chord("D/F#"), -2).name == "C/E"
    assert transpose_chord(parse_chord("C"), -1).name == "B"
