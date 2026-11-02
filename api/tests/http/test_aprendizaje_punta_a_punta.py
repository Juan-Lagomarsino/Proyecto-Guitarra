"""F5-T11: una canción nueva usa lo aprendido en otra (API + core; el worker lo ve en su test).

Recorrido: la canción A (capo 2) tiene un riff automático y un acorde; Juan Pedro corrige por PUT
la digitación de las notas y elige otra forma de Am. La canción B (sin capo) recibe un claim de
separación con las preferencias, y con ellas el código de core elige las posiciones corregidas.

El worker no se importa desde la API: el claim de B se guarda en
`worker/tests/fixtures/claim_con_aprendizaje.json` y `worker/tests/test_aprende_de_correcciones.py`
lo consume con `build_riffs` real. Este test falla si el claim cambia; para regenerar el archivo
correr con `REGENERAR_FIXTURE=1`.
"""

import copy
import json
import os
from pathlib import Path

import pytest
import test_jobs_api as base
from guitarra_core.chord_preferences import ChordShapePreferences
from guitarra_core.fingering import FingeringPreferences, finger_notes
from guitarra_core.instrument import voicings_for
from test_jobs_api import UI, chart_json, claim, new_song, post_result, result_body

# Fixtures reutilizadas de la API de la cola.
client, clock, jobs, songs = base.client, base.clock, base.jobs, base.songs

FIXTURE = (
    Path(__file__).resolve().parents[3] / "worker" / "tests" / "fixtures"
    / "claim_con_aprendizaje.json"
)  # fmt: skip
CAPO_A = 2
BPM = 100
PITCHES = [57, 59, 60, 62]  # A3 B3 C4 D4
# Lo automático (relativo al capo 2) y lo que elige el usuario (relativo al capo 2).
AUTO_FRETS = [(3, 0), (3, 2), (3, 3), (2, 1)]
USER_FRETS = [(4, 5), (4, 7), (4, 8), (3, 5)]
# En el mástil (absoluto): lo que debe elegir B sin capo.
EXPECTED_ABSOLUTE = [(4, 7), (4, 9), (4, 10), (3, 7)]
AM_BARRE = [5, 7, 7, 5, 5, 5]  # absoluta; con capo 2 es [3, 5, 5, 3, 3, 3]


def riff_with(frets):
    events = [
        {"t": float(i), "dur": 1, "string": s, "fret": f, "confidence": 0.8}
        for i, (s, f) in enumerate(frets)
    ]
    return {"bpm": BPM, "events": events}


def chart_url(song_id):
    return f"/api/v1/songs/{song_id}/chart?instrument=electric"


def put_edit(client, song_id, edit):
    body = copy.deepcopy(client.get(chart_url(song_id), headers=UI).json()["content"])
    edit(body["sections"][0])
    response = client.put(chart_url(song_id), json=body, headers=UI)
    assert response.status_code == 200, response.text


def song_a_con_riff_automatico(client, songs, jobs):
    song = new_song(songs, youtube_id="cancion-a", title="Canción A")
    jobs.add_job(song.id)
    job = claim(client).json()
    chart = {**chart_json("electric"), "capo": CAPO_A}
    assert post_result(client, job["job_id"], result_body(charts=[chart])).status_code == 200
    separation = claim(client).json()
    assert separation["job_type"] == "separation"
    body = {"worker_id": "w1", "riffs": {"intro": riff_with(AUTO_FRETS)}}
    assert post_result(client, separation["job_id"], body).status_code == 200
    return song


def correct_notes_one_by_one(client, song_id):
    """Cuatro correcciones de digitación (misma altura, otra posición), una nota más cada vez."""
    current = list(AUTO_FRETS)
    for index in range(len(current)):
        current[index] = USER_FRETS[index]
        put_edit(client, song_id, lambda s, c=list(current): s.update(riff=riff_with(c)))


def choose_other_chord_shape(client, song_id):
    put_edit(client, song_id, lambda s: s["chords"][0].update(shape=[3, 5, 5, 3, 3, 3]))


def separation_claim_for_b(client, songs, jobs):
    song = new_song(songs, youtube_id="cancion-b", title="Canción B")
    jobs.add_job(song.id)
    job = claim(client).json()
    assert post_result(client, job["job_id"], result_body()).status_code == 200  # capo 0
    separation = claim(client).json()
    assert separation["job_type"] == "separation"
    return separation


@pytest.fixture
def claim_b(client, songs, jobs):
    song_a = song_a_con_riff_automatico(client, songs, jobs)
    correct_notes_one_by_one(client, song_a.id)
    choose_other_chord_shape(client, song_a.id)
    return separation_claim_for_b(client, songs, jobs)


def test_el_claim_de_la_cancion_nueva_trae_lo_aprendido(claim_b):
    assert claim_b["chart"]["capo"] == 0
    fingering = claim_b["fingering_preferences"]
    assert fingering["positions"] and fingering["zones"]
    assert set(fingering["positions"]) == {str(p) for p in PITCHES}
    assert claim_b["chord_shape_preferences"] == {
        "electric": {"Am": {",".join(map(str, AM_BARRE)): pytest.approx(0.3)}}
    }


def test_core_elige_en_la_cancion_nueva_las_posiciones_corregidas(claim_b):
    preferences = FingeringPreferences.from_json(claim_b["fingering_preferences"])
    sin_aprender = finger_notes(PITCHES)
    aprendido = finger_notes(PITCHES, preferences=preferences.for_capo(0))
    assert [(p.string, p.fret) for p in sin_aprender] != EXPECTED_ABSOLUTE
    assert [(p.string, p.fret) for p in aprendido] == EXPECTED_ABSOLUTE


def test_core_elige_la_forma_de_acorde_del_usuario_con_otro_capo(claim_b):
    preferences = ChordShapePreferences.from_json(claim_b["chord_shape_preferences"])
    for capo in (0, 2):
        [voicing] = voicings_for(["Am"], "electric", capo, False, preferences)
        assert voicing.shape is not None
        assert list(voicing.shape.shape) == [f - capo for f in AM_BARRE]


def test_fixture_del_claim_para_el_worker_esta_al_dia(claim_b):
    wanted = {
        key: claim_b[key]
        for key in ("job_type", "chart", "fingering_preferences", "chord_shape_preferences")
    }
    text = json.dumps(wanted, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("REGENERAR_FIXTURE") == "1":
        FIXTURE.write_text(text, encoding="utf-8", newline="\n")
    assert FIXTURE.read_text(encoding="utf-8") == text, "regenerar con REGENERAR_FIXTURE=1"
