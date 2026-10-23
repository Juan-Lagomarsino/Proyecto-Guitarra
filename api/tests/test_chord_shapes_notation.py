"""Toda forma de guitarra_core valida con el modelo `Chord` de la notación."""

import pytest
from guitarra_core.chord_shapes import shapes_for

from guitarra_api.domain.notation import Chord

NAMES = [
    "C", "G", "D", "A", "E", "F", "Am", "Em", "Dm", "Bm", "F#m", "Bb",
    "G7", "C7", "Cmaj7", "Am7", "Dsus4", "Asus2", "Cadd9", "B7", "C/G", "D/F#", "Fmaj7#11",
]  # fmt: skip


@pytest.mark.parametrize("name", NAMES)
def test_every_generated_shape_validates_with_notation_chord(name):
    shapes = shapes_for(name)
    assert shapes
    for shape in shapes:
        chord = Chord.model_validate({"t": 0, "name": name, **shape.to_notation()})
        assert len(chord.shape) == 6
