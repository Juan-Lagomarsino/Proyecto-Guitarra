import pytest

from guitarra_worker.domain.chords import (
    ChordSpan,
    RawChord,
    normalize_label,
    snap_to_beats,
)

BEATS = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


def raw(*items):
    return [RawChord(start, end, label) for start, end, label in items]


def test_normaliza_etiquetas_de_btc_al_nombre_del_core():
    assert normalize_label("C") == "C"
    assert normalize_label("A:min") == "Am"
    assert normalize_label("D#:min7") == "Ebm7"
    assert normalize_label("B:7") == "B7"
    assert normalize_label("E:hdim7") == "Em7b5"
    assert normalize_label("G:sus4") == "Gsus4"


@pytest.mark.parametrize("label", ["N", "X", "", "???"])
def test_sin_acorde_se_normaliza_a_N(label):
    assert normalize_label(label) == "N"


def test_acordes_que_coinciden_con_la_grilla_conservan_tiempos_y_confianza_total():
    spans = snap_to_beats(raw((0.0, 1.5, "C"), (1.5, 3.5, "G")), BEATS)
    assert spans == [ChordSpan(0.0, 1.5, "C", 1.0), ChordSpan(1.5, 3.5, "G", 1.0)]


def test_los_cambios_se_ajustan_al_beat_por_mayoria():
    # El cambio real es en 1.1 s: el beat 1.0-1.5 es mayormente de G.
    spans = snap_to_beats(raw((0.0, 1.1, "C"), (1.1, 3.5, "G")), BEATS)
    assert [(s.start, s.end, s.label) for s in spans] == [(0.0, 1.0, "C"), (1.0, 3.5, "G")]


def test_un_acorde_de_menos_de_un_beat_se_fusiona_con_el_vecino():
    spans = snap_to_beats(raw((0.0, 1.0, "C"), (1.0, 1.2, "F"), (1.2, 3.5, "C")), BEATS)
    assert [s.label for s in spans] == ["C"]
    assert (spans[0].start, spans[0].end) == (0.0, 3.5)


def test_la_confianza_del_tramo_es_el_promedio_por_duracion_de_sus_beats():
    spans = snap_to_beats(raw((0.0, 1.25, "C"), (1.25, 3.5, "G")), BEATS)
    # C: dos beats completos (1.0) y el tercero con 0.25 de 0.5 (0.5).
    assert [s.label for s in spans] == ["C", "G"]
    assert spans[0].end == 1.5
    assert spans[0].confidence == pytest.approx((1.0 + 1.0 + 0.5) / 3)
    assert spans[1].confidence == pytest.approx(1.0)


def test_el_beat_repartido_tiene_menos_confianza_que_uno_limpio():
    spans = snap_to_beats(raw((0.0, 1.2, "C"), (1.2, 3.5, "G")), BEATS)
    assert spans[0].label == "C"
    assert spans[0].end == 1.0
    assert spans[1].label == "G"
    assert spans[1].confidence < 1.0  # el beat 1.0-1.5 es 60 % G


def test_la_ultima_celda_usa_la_mediana_del_periodo_de_beat():
    spans = snap_to_beats(raw((0.0, 10.0, "C")), [0.0, 0.5, 1.0, 1.6])
    assert spans[-1].end == pytest.approx(2.1)  # 1.6 + mediana(0.5, 0.5, 0.6) = 0.5


def test_la_duracion_del_audio_recorta_la_grilla():
    spans = snap_to_beats(raw((0.0, 10.0, "C")), BEATS, duration_s=2.2)
    assert spans[-1].end == pytest.approx(2.2)


def test_silencio_es_N_con_confianza_total():
    spans = snap_to_beats(raw((0.0, 3.5, "N")), BEATS)
    assert [(s.label, s.confidence) for s in spans] == [("N", 1.0)]


def test_zona_sin_cobertura_es_N_con_confianza_cero():
    spans = snap_to_beats([], BEATS)
    assert [(s.label, s.confidence) for s in spans] == [("N", 0.0)]


def test_un_acorde_unico_da_un_solo_tramo():
    spans = snap_to_beats(raw((0.0, 3.5, "A:min")), BEATS)
    assert [(s.label, s.start) for s in spans] == [("Am", 0.0)]


@pytest.mark.parametrize("beats", [[], [1.0]])
def test_sin_grilla_suficiente_no_hay_tramos(beats):
    assert snap_to_beats(raw((0.0, 3.5, "C")), beats) == []


def test_ignora_beats_duplicados_o_desordenados():
    spans = snap_to_beats(raw((0.0, 3.5, "C")), [1.0, 0.0, 0.5, 0.5, 1.5])
    assert (spans[0].start, spans[0].end) == (0.0, 2.0)
