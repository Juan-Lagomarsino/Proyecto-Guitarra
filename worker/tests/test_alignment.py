import pytest

from guitarra_worker.domain.alignment import (
    align,
    blend_confidence,
    parse_chord,
    transpose_chord,
)

PROG = ["G", "B7", "Em", "C", "G", "D"]


def test_iguales_dan_similitud_total():
    result = align(PROG, list(PROG))
    assert result.transposition == 0
    assert result.distance == 0
    assert result.similarity == 1.0
    assert result.pairs == [(i, i) for i in range(len(PROG))]


def test_transpuesta_se_detecta_y_se_alinea():
    detected = [transpose_chord(c, 2) for c in PROG]  # suena 2 semitonos más (capo)
    result = align(PROG, detected)
    assert result.transposition == 2
    assert result.similarity == 1.0


def test_sin_transposicion_no_la_busca():
    detected = [transpose_chord(c, 2) for c in PROG]
    assert align(PROG, detected, allow_transposition=False).similarity < 0.5


def test_insercion_en_lo_detectado():
    detected = ["G", "B7", "F#", "Em", "C", "G", "D"]
    result = align(PROG, detected)
    assert result.transposition == 0
    assert (None, 2) in result.pairs
    assert 0.8 < result.similarity < 1.0


def test_omision_en_lo_detectado():
    detected = ["G", "B7", "C", "G", "D"]
    result = align(PROG, detected)
    assert (2, None) in result.pairs
    assert result.similarity == pytest.approx(5 / 6)


def test_misma_raiz_distinta_calidad_cuesta_menos_que_otra_raiz():
    cerca = align(["G"], ["Gm"], allow_transposition=False)
    lejos = align(["G"], ["D"], allow_transposition=False)
    assert 0 < cerca.distance < lejos.distance


def test_equivalencia_enarmonica():
    assert align(["Bb", "F"], ["A#", "F"]).similarity == 1.0


def test_vacias():
    assert align([], []).similarity == 0.0
    assert align(PROG, []).similarity == 0.0


def test_acorde_ilegible_no_rompe():
    assert parse_chord("N.C.") is None
    result = align(["G", "N.C.", "D"], ["G", "D"])
    assert (0, 0) in result.pairs
    assert result.similarity > 0.5


def test_transpose_chord_con_bajo():
    assert transpose_chord("C/G", 2) == "D/A"
    assert transpose_chord("Am7", -3) == "F#m7"


def test_mezcla_de_confianza():
    assert blend_confidence(0.6, 1.0) > 0.6
    assert blend_confidence(0.6, 0.0) < 0.6
    assert blend_confidence(0.6, 0.5) == pytest.approx(0.6, abs=0.1)
    assert 0.0 <= blend_confidence(1.0, 1.0) <= 1.0
    assert 0.0 <= blend_confidence(0.0, 0.0) <= 1.0
