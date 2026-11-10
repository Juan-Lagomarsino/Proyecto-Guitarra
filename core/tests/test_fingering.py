import time

import pytest

from guitarra_core.fingering import (
    FingeringCosts,
    FingeringError,
    FingeringPreferences,
    FingeringStep,
    UnplayableNoteError,
    _prune,
    _State,
    finger_notes,
    finger_steps,
)

# Pentatónica menor de La, posición 5 (E2 = 40, A2 = 45, ...)
PENTATONIC_A = [45, 48, 50, 52, 55, 57, 60, 62, 64, 67, 69]


def frets(placements):
    return [(p.string, p.fret) for p in placements]


def test_pentatonica_se_queda_en_una_posicion():
    placed = finger_notes([45 + 12, 60, 62, 64, 67, 69])
    pressed = [p.fret for p in placed if p.fret > 0]
    assert max(pressed) - min(pressed) <= 4


def test_escala_ascendente_no_salta_de_zona():
    placed = finger_notes(PENTATONIC_A)
    assert all(p.fret <= 8 for p in placed)
    assert [p.midi for p in placed] == PENTATONIC_A


def test_nota_grave_va_a_cuerda_al_aire_o_baja():
    (placed,) = finger_notes([40])
    assert (placed.string, placed.fret) == (6, 0)


def test_salto_de_octava_cambia_de_zona_solo_si_conviene():
    # Mi3 -> Mi4: la octava se toca cerca de la mano, no se muda de zona
    near = finger_notes([52, 64])
    pressed = [p.fret for p in near if p.fret > 0]
    assert max(pressed) - min(pressed) <= 4
    # Si la nota obliga (Mi5 solo existe en la zona alta), la mano sí cambia de zona
    far = finger_notes([52, 76])
    assert far[1].fret >= 12
    # Y vuelve: ir y volver a la misma nota da la misma digitación
    back = finger_notes([57, 69, 57])
    assert back[0] == back[2]


def test_double_stop_en_cuerdas_distintas_y_estiramiento_acotado():
    ((a, b),) = finger_steps([FingeringStep((57, 64))])
    assert a.string != b.string
    pressed = [p.fret for p in (a, b) if p.fret > 0]
    assert not pressed or max(pressed) - min(pressed) <= 4


def test_power_chord_en_cuerdas_distintas():
    ((root, fifth, octave),) = finger_steps([FingeringStep((45 + 3, 45 + 10, 45 + 15))])
    assert len({root.string, fifth.string, octave.string}) == 3
    pressed = [p.fret for p in (root, fifth, octave)]
    assert max(pressed) - min(pressed) <= 4


def test_acorde_imposible_por_estiramiento_da_error():
    # Do2 (fuera de rango en cuerdas) no; usamos dos notas que solo entran muy separadas
    with pytest.raises(FingeringError):
        finger_steps([FingeringStep((40 + 0, 40 + 12, 40 + 24, 40 + 36, 40 + 48, 40 + 60))])


def test_mas_notas_que_cuerdas_da_error():
    with pytest.raises(FingeringError, match="cuerdas"):
        finger_steps([FingeringStep((40, 45, 50, 55, 59, 64, 67))])


def test_paso_vacio_da_error():
    with pytest.raises(FingeringError):
        finger_steps([FingeringStep(())])


def test_nota_fuera_de_rango_informa_altura_e_indice():
    with pytest.raises(UnplayableNoteError) as info:
        finger_notes([45, 52, 30])
    assert info.value.pitch == 30
    assert info.value.index == 2
    assert "30" in str(info.value)
    with pytest.raises(UnplayableNoteError):
        finger_notes([64 + 23])  # un traste más allá del 22


def test_capo_cuenta_trastes_desde_el_capo():
    # Con capo 2 la cuerda 6 al aire suena Fa# (42): traste 0 relativo
    (placed,) = finger_notes([42], capo=2)
    assert (placed.string, placed.fret) == (6, 0)
    with pytest.raises(UnplayableNoteError):
        finger_notes([41], capo=2)


def test_afinacion_distinta():
    drop_d = (38, 45, 50, 55, 59, 64)
    (placed,) = finger_notes([38], tuning=drop_d)
    assert (placed.string, placed.fret) == (6, 0)


def test_cuerdas_al_aire_con_costo_configurable():
    # Sol3 (55): al aire en la 3ra cuerda o traste 5 de la 4ta
    cheap = finger_notes([55, 55], costs=FingeringCosts(open_string=-1.0))
    pricey = finger_notes([55, 55], costs=FingeringCosts(open_string=5.0))
    assert all(p.fret == 0 for p in cheap)
    assert all(p.fret > 0 for p in pricey)


def test_aire_levemente_favorable_en_registro_grave():
    (low,) = finger_notes([45])  # La2: al aire en la 5ta
    assert (low.string, low.fret) == (5, 0)


def test_preferencia_fuerte_por_posicion_cambia_la_digitacion():
    # La2 (45): por defecto al aire en la 5ta cuerda; el usuario prefiere el traste 5 de la 6ta
    (default,) = finger_notes([45])
    assert (default.string, default.fret) == (5, 0)
    strong = FingeringPreferences(positions={45: {"6,5": 1.0}})
    (preferred,) = finger_notes([45], preferences=strong)
    assert (preferred.string, preferred.fret) == (6, 5)


def test_preferencia_debil_no_cambia_la_digitacion():
    weak = FingeringPreferences(positions={45: {"6,5": 0.02}})
    assert finger_notes([45], preferences=weak) == finger_notes([45])


def test_preferencia_por_zona():
    # Mi3 (52): traste 2 de la 4ta, 7 de la 5ta o 12 de la 6ta... con zona 1 (trastes 4 a 7)
    (default,) = finger_notes([52])
    prefs = FingeringPreferences(zones={1: 1.0})
    (zoned,) = finger_notes([52], preferences=prefs)
    assert default.fret != zoned.fret
    assert 4 <= zoned.fret <= 7


def test_preferencias_json_ida_y_vuelta():
    data = {"positions": {"69": {"5,12": 0.8, "1,5": 0.1}}, "zones": {"1": 0.5}}
    prefs = FingeringPreferences.from_json(data)
    assert prefs.position_weight(69, 5, 12) == 0.8
    assert prefs.zone_weight(5) == 0.5
    assert prefs.to_json() == {
        "positions": {"69": {"1,5": 0.1, "5,12": 0.8}},
        "zones": {"1": 0.5},
    }
    assert FingeringPreferences.from_json(None).to_json() == {"positions": {}, "zones": {}}


def test_pesos_se_recortan_a_uno():
    prefs = FingeringPreferences(positions={60: {"1,1": 50.0}}, zones={0: -3.0})
    assert prefs.position_weight(60, 1, 1) == 1.0
    assert prefs.zone_weight(1) == 0.0


def test_determinismo():
    notes = [60, 64, 67, 72, 67, 64, 60] * 5
    first = finger_notes(notes)
    assert all(finger_notes(notes) == first for _ in range(3))


def test_secuencia_vacia():
    assert finger_steps([]) == []


def test_rendimiento_500_notas():
    notes = [PENTATONIC_A[(i * 7) % len(PENTATONIC_A)] for i in range(500)]
    start = time.perf_counter()
    placed = finger_notes(notes)
    assert time.perf_counter() - start < 1.0
    assert len(placed) == 500


@pytest.mark.parametrize(
    "notes",
    [
        [45, 57, 45, 57, 45, 59, 45, 60],
        [40, 52, 40, 52, 40, 55, 40, 56],
    ],
)
def test_la_mano_recuerda_su_posicion_tras_cuerdas_al_aire(notes):
    placed = finger_notes(notes)
    assert max(p.fret for p in placed) <= 6


def test_la_mano_recuerda_la_posicion_alta_tras_cuerdas_al_aire():
    # 76, 77 y 79 solo existen desde el traste 12: se quedan juntos, sin saltar de zona
    placed = finger_notes([64, 76, 64, 77, 64, 79])
    pressed = [p.fret for p in placed if p.fret > 0]
    assert pressed == [12, 13, 15]


def test_riff_en_registro_medio_no_se_va_arriba_por_evitar_cambiar_de_cuerda():
    placed = finger_notes([55, 57, 59, 60, 59, 57, 55, 57])
    assert max(p.fret for p in placed) <= 7


def test_pentatonica_en_posicion_5_queda_dentro_de_cinco_trastes():
    placed = finger_notes([57, 60, 62, 64, 67, 69, 67, 64, 62, 60, 57])
    pressed = [p.fret for p in placed if p.fret > 0]
    assert max(pressed) - min(pressed) <= 5
    assert max(pressed) <= 8


TWO_STRINGS = (40, 60)


def test_span_de_cinco_trastes_forzado_es_error_y_cuatro_pasa():
    with pytest.raises(FingeringError):
        finger_steps([FingeringStep((45, 70))], tuning=TWO_STRINGS)  # trastes 5 y 10
    ((low, high),) = finger_steps([FingeringStep((45, 69))], tuning=TWO_STRINGS)  # 5 y 9
    assert (low.fret, high.fret) == (5, 9)


def test_aire_mas_traste_siete_es_valido():
    ((low, high),) = finger_steps([FingeringStep((40, 67))], tuning=TWO_STRINGS)
    assert (low.fret, high.fret) == (0, 7)


def test_poda_conserva_diversidad_de_mano():
    def state(hand, cost):
        return _State((), hand, 1.0, cost)

    states = [state(2, 0.0), state(2, 0.1), state(2, 0.2), state(9, 5.0), state(None, 6.0)]
    kept = _prune(states, 3)
    assert {s.hand for s in kept} == {2, 9, None}
    assert len(kept) == 3
    assert _prune(states, 10) == sorted(states, key=lambda s: s.cost)


def test_preferencias_con_clave_invalida_dan_error_claro():
    with pytest.raises(ValueError, match="cuerda,traste"):
        FingeringPreferences.from_json({"positions": {"60": {"abc": 1.0}}})


def test_to_json_recorta_pesos():
    prefs = FingeringPreferences(positions={60: {"1,1": 50.0}}, zones={0: -3.0})
    assert prefs.to_json() == {"positions": {"60": {"1,1": 1.0}}, "zones": {"0": 0.0}}


def test_for_capo_resta_el_capo_a_claves_y_zonas():
    absolute = FingeringPreferences(
        positions={59: {"3,4": 0.6, "4,9": 0.2}}, zones={1: 0.5, 2: 0.4}
    )
    relative = absolute.for_capo(2)
    assert relative.positions == {59: {"3,2": 0.6, "4,7": 0.2}}
    # zona 1 = trastes 4-7 -> 2-5 (zona 0); zona 2 = 8-11 -> 6-9 (zona 1)
    assert relative.zones == {0: 0.5, 1: 0.4}


def test_for_capo_descarta_posiciones_bajo_el_capo():
    absolute = FingeringPreferences(positions={55: {"3,0": 0.9, "3,2": 0.4}}, zones={0: 0.7})
    relative = absolute.for_capo(2)
    assert relative.positions == {55: {"3,0": 0.4}}
    assert relative.zones == {0: 0.7}  # la zona 0 absoluta (0-3) todavia cubre trastes 2-3


def test_for_capo_descarta_zonas_enteras_bajo_el_capo():
    relative = FingeringPreferences(zones={0: 0.7, 1: 0.2}).for_capo(5)
    assert relative.zones == {0: 0.2}


def test_for_capo_cero_es_identidad_y_no_deja_entradas_vacias():
    prefs = FingeringPreferences(positions={55: {"3,0": 0.9}}, zones={0: 0.7})
    assert prefs.for_capo(0) == prefs
    assert FingeringPreferences(positions={55: {"3,1": 0.9}}).for_capo(3).positions == {}
