import pytest

from guitarra_worker.domain.chords import ChordSpan
from guitarra_worker.domain.key import KEY_CONFIDENCE_CAP, detect_key


def spans(*items):
    t, out = 0.0, []
    for label, duration in items:
        out.append(ChordSpan(t, t + duration, label, 1.0))
        t += duration
    return out


def test_progresion_en_sol_mayor():
    key = detect_key(spans(("G", 4), ("C", 2), ("D", 2), ("G", 4), ("Em", 2)))
    assert (key.tonic, key.mode) == ("G", "major")
    assert key.name == "G"
    assert key.relative == "Em"


def test_progresion_en_la_menor():
    key = detect_key(spans(("Am", 4), ("Dm", 2), ("E", 2), ("Am", 4), ("G", 1), ("F", 1)))
    assert (key.tonic, key.mode) == ("A", "minor")
    assert key.name == "Am"
    assert key.relative == "C"


def test_el_peso_es_la_duracion():
    key = detect_key(spans(("D", 20), ("A", 6), ("G", 6), ("C", 1)))
    assert key.tonic == "D"


def test_la_confianza_tiene_techo():
    key = detect_key(spans(("G", 4), ("C", 2), ("D", 2), ("G", 4)))
    assert 0 < key.confidence <= KEY_CONFIDENCE_CAP


def test_silencio_no_tiene_tonalidad():
    assert detect_key(spans(("N", 10))) is None


def test_sin_tramos_no_tiene_tonalidad():
    assert detect_key([]) is None


def test_un_solo_acorde_da_una_tonalidad_con_confianza_acotada():
    key = detect_key(spans(("C", 5)))
    assert key is not None
    assert key.tonic == "C"
    assert key.confidence <= KEY_CONFIDENCE_CAP


@pytest.mark.parametrize("label", ["Bbm7", "Esus4", "Cdim"])
def test_acepta_calidades_extendidas(label):
    assert detect_key(spans((label, 4), ("G", 4))) is not None


def test_etiqueta_ilegible_se_trata_como_sin_acorde():
    corrupta = detect_key(spans(("G", 4), ("C", 2), ("D", 2), ("G", 4), ("???", 6)))
    limpia = detect_key(spans(("G", 4), ("C", 2), ("D", 2), ("G", 4)))
    assert corrupta == limpia


def test_solo_etiquetas_ilegibles_no_tiene_tonalidad():
    assert detect_key(spans(("???", 5))) is None
