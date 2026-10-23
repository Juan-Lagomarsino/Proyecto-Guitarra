import pytest

from guitarra_worker.domain.chart_assembly import (
    match_with_cifra,
    merge_detected,
    plan_sections,
    section_drafts,
    section_id,
)


def span(start, end, label, confidence=0.8):
    return {"start": start, "end": end, "label": label, "confidence": confidence}


def test_merge_junta_repetidos_seguidos_y_saca_los_silencios():
    raw = [
        span(0, 1, "Am"),
        span(1, 2, "Am", 0.4),
        span(2, 3, "N"),
        span(3, 4, "Am"),
        span(4, 5, "G"),
    ]
    merged = merge_detected(raw)
    assert [(c.start, c.end, c.label) for c in merged] == [
        (0, 2, "Am"),
        (3, 4, "Am"),
        (4, 5, "G"),
    ]
    assert merged[0].confidence == pytest.approx(0.6)


def test_merge_de_lista_vacia():
    assert merge_detected([]) == []


def test_secciones_se_ordenan_y_no_se_solapan():
    structure = [
        {"start_s": 5.0, "end_s": 10.0, "name": None, "group": "B"},
        {"start_s": 0.0, "end_s": 6.0, "name": None, "group": "A"},
    ]
    drafts = section_drafts(structure, 10.0)
    assert [(d.start_s, d.end_s, d.group) for d in drafts] == [(0.0, 6.0, "A"), (6.0, 10.0, "B")]


def test_seccion_degenerada_se_descarta():
    structure = [
        {"start_s": 0.0, "end_s": 5.0, "name": "X", "group": "A"},
        {"start_s": 4.0, "end_s": 5.0, "name": "Y", "group": "B"},
    ]
    assert [d.name for d in section_drafts(structure, 5.0)] == ["X"]


def test_sin_secciones_ni_duracion_es_error():
    with pytest.raises(ValueError):
        section_drafts([], 0.0)


def test_acorde_que_cruza_el_hueco_va_a_la_siguiente_seccion_desde_su_inicio():
    drafts = section_drafts(
        [
            {"start_s": 2.0, "end_s": 6.0, "name": "A", "group": None},
            {"start_s": 8.0, "end_s": 12.0, "name": "B", "group": None},
        ],
        12.0,
    )
    detected = merge_detected([span(0, 4, "Am"), span(6, 9, "G"), span(9, 12, "C")])
    plans = plan_sections(drafts, detected, None)
    assert [(c.t_s, c.name) for c in plans[0].chords] == [(2.0, "Am")]
    assert [(c.t_s, c.name) for c in plans[1].chords] == [(8.0, "G"), (9.0, "C")]


def test_sin_cifra_o_sin_detectados_no_hay_cruce():
    detected = merge_detected([span(0, 1, "Am")])
    assert match_with_cifra(None, detected) is None
    assert match_with_cifra({"found": False}, detected) is None
    cifra = {"found": True, "sections": [{"name": "I", "chords": ["Am"]}]}
    assert match_with_cifra(cifra, []) is None


def test_section_id_sin_tildes_ni_simbolos_y_con_indice():
    assert section_id("Refrão (2x)", 2) == "03-refrao-2x"
    assert section_id("¿¿??", 0) == "01-seccion"
