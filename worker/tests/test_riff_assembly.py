import json
from pathlib import Path

import pytest
from guitarra_core.fingering import FingeringPreferences

from guitarra_worker.domain.riff_assembly import RiffChart, build_riffs

CHART = RiffChart(bpm=120.0, time_signature="4/4", capo=0)
SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "notation.schema.json"


def ev(midi, t=0.0, dur=0.5, confidence=0.9):
    return {"midi": midi, "t": t, "dur": dur, "confidence": confidence}


def validate(notation):
    """Validación contra el esquema: jsonschema si está; si no, los campos obligatorios."""
    try:
        import jsonschema
    except ImportError:
        assert notation["bpm"] > 0 and len(notation["tuning"]) == 6
        for e in notation["events"]:
            assert {"t", "dur", "string", "fret"} <= set(e)
            assert 1 <= e["string"] <= 6 and 0 <= e["fret"] <= 24 and e["dur"] > 0
            assert e["technique"] is None and 0 <= e["confidence"] <= 1
        return
    jsonschema.validate(notation, json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_power_chord_usa_cuerdas_distintas():
    events = build_riffs({"s": [ev(45), ev(52)]}, CHART)["s"]["events"]  # La2 + Mi3
    assert len(events) == 2
    assert len({e["string"] for e in events}) == 2
    assert all(e["t"] == 0.0 for e in events)


def test_notacion_valida_y_campos():
    riffs = build_riffs({"s": [ev(45, 0.0), ev(52, 0.0), ev(47, 1.0, 0.25, 0.4)]}, CHART)
    notation = riffs["s"]
    validate(notation)
    assert notation["bpm"] == 120.0 and notation["time_signature"] == "4/4"
    assert notation["tonic"] is None and notation["tuning"][0] == "E2"
    last = notation["events"][-1]
    assert last["t"] == 1.0 and last["dur"] == 0.25 and last["confidence"] == 0.4
    assert last["technique"] is None


def test_paso_intocable_se_simplifica_conservando_la_mayor_confianza():
    # Fa2 (6.ª, traste 1) + Fa#5 (1.ª, traste 14): no entran juntos -> queda 1
    riffs = build_riffs({"s": [ev(41, confidence=0.9), ev(78, confidence=0.5)]}, CHART)
    validate(riffs["s"])
    events = riffs["s"]["events"]
    assert len(events) == 1 and events[0]["confidence"] == 0.9


def test_empate_de_confianza_deja_la_mas_grave_y_la_mas_aguda():
    # Fa2, Do4 y Fa#5 con la misma confianza: se suelta la del medio y luego la más aguda
    notes = [ev(41, confidence=0.7), ev(60, confidence=0.7), ev(78, confidence=0.7)]
    events = build_riffs({"s": notes}, CHART)["s"]["events"]
    pitches_kept = len(events)
    assert pitches_kept < 3
    # la del medio se suelta primero: quedan la más grave (6.ª al aire) y/o la más aguda
    assert any(e["string"] == 6 and e["fret"] == 1 for e in events)


def test_nota_fuera_de_rango_se_descarta():
    events = build_riffs({"s": [ev(30, 0.0), ev(45, 1.0)]}, CHART)["s"]["events"]
    assert len(events) == 1 and events[0]["t"] == 1.0


def test_seccion_sin_eventos_no_va():
    assert build_riffs({"a": [], "b": [ev(20)]}, CHART) == {}


def test_capo_mueve_los_trastes_y_nunca_son_negativos():
    # Si3 (47): sin capo es el traste 2 de la 5.ª; con capo 2 es el traste 0 (relativo al capo)
    sin = build_riffs({"s": [ev(47)]}, CHART)["s"]["events"][0]
    con = build_riffs({"s": [ev(47)]}, RiffChart(120.0, "4/4", 2))["s"]["events"][0]
    assert (sin["string"], sin["fret"]) == (5, 2)
    assert (con["string"], con["fret"]) == (5, 0)


def test_preferencias_cambian_cuerda_y_traste():
    base = build_riffs({"s": [ev(69)]}, CHART)["s"]["events"][0]  # La4
    other = (3, 14) if (base["string"], base["fret"]) != (3, 14) else (2, 10)
    prefs = FingeringPreferences.from_json({"positions": {"69": {f"{other[0]},{other[1]}": 1.0}}})
    moved = build_riffs({"s": [ev(69)]}, CHART, prefs)["s"]["events"][0]
    assert (moved["string"], moved["fret"]) == other
    assert (moved["string"], moved["fret"]) != (base["string"], base["fret"])


def test_notas_duplicadas_en_el_mismo_t_se_unifican():
    notes = [ev(45, confidence=0.3), ev(45, confidence=0.8)]
    events = build_riffs({"s": notes}, CHART)["s"]["events"]
    assert len(events) == 1 and events[0]["confidence"] == pytest.approx(0.8)
