"""F5-T11: el worker usa lo aprendido de las correcciones del usuario.

Consume `fixtures/claim_con_aprendizaje.json`, el claim de separación de una canción nueva (B) tras
corregir riffs y un acorde en otra (A, con capo 2). Lo genera y verifica
`api/tests/http/test_aprendizaje_punta_a_punta.py` (regenerar con `REGENERAR_FIXTURE=1`).
"""

import json
from pathlib import Path

import pytest
from guitarra_core.chord_preferences import ChordShapePreferences
from guitarra_core.fingering import FingeringPreferences
from guitarra_core.instrument import voicings_for

from guitarra_worker.domain.riff_assembly import RiffChart, build_riffs

CLAIM = json.loads(
    (Path(__file__).parent / "fixtures" / "claim_con_aprendizaje.json").read_text(encoding="utf-8")
)
PITCHES = [57, 59, 60, 62]  # A3 B3 C4 D4
LEARNED = [(4, 7), (4, 9), (4, 10), (3, 7)]  # (cuerda, traste) del mástil
AM_BARRE = [5, 7, 7, 5, 5, 5]


def notes():
    return [
        {"midi": midi, "t": float(i), "dur": 0.5, "confidence": 0.9}
        for i, midi in enumerate(PITCHES)
    ]


def placements(preferences):
    chart = RiffChart(bpm=CLAIM["chart"]["bpm"], capo=CLAIM["chart"]["capo"])
    events = build_riffs({"intro": notes()}, chart, preferences)["intro"]["events"]
    return [(e["string"], e["fret"]) for e in events]


def test_sin_preferencias_el_armado_no_elige_las_corregidas():
    assert placements(None) != LEARNED


def test_con_las_preferencias_del_claim_el_armado_elige_las_corregidas():
    preferences = FingeringPreferences.from_json(CLAIM["fingering_preferences"])
    assert CLAIM["job_type"] == "separation" and CLAIM["chart"]["capo"] == 0
    assert placements(preferences.for_capo(CLAIM["chart"]["capo"])) == LEARNED


def test_aprendido_en_la_cancion_con_capo_vale_en_la_que_no_tiene():
    # Las preferencias viajan absolutas: con capo 2 las mismas posiciones salen 2 trastes menos.
    preferences = FingeringPreferences.from_json(CLAIM["fingering_preferences"])
    chart = RiffChart(bpm=100.0, capo=2)
    events = build_riffs({"intro": notes()}, chart, preferences.for_capo(2))["intro"]["events"]
    assert [(e["string"], e["fret"] + 2) for e in events] == LEARNED


@pytest.mark.parametrize("capo", [0, 2])
def test_la_forma_de_acorde_elegida_se_usa_en_la_cancion_nueva(capo):
    preferences = ChordShapePreferences.from_json(CLAIM["chord_shape_preferences"])
    [voicing] = voicings_for(["Am"], "electric", capo, False, preferences)
    assert list(voicing.shape.shape) == [fret - capo for fret in AM_BARRE]
