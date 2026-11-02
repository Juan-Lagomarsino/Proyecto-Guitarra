import pytest

from guitarra_api.domain.notation import Notation
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.domain.song_exercise import (
    SectionNotFoundInChartError,
    SectionNotPlayableError,
    build_section_exercise,
    complete_with_events,
)

AM = ["x", 0, 2, 2, 1, 0]
F = [1, 3, 3, 2, 1, 1]


def chord(t_s, name="Am", shape=AM):
    return {"t_s": t_s, "name": name, "shape": shape, "confidence": 0.9}


def content(section=None, bpm=120, **extra) -> SongChartContent:
    base = {
        "id": "verso",
        "name": "Verso",
        "start_s": 10,
        "end_s": 26,
        "order": 0,
        "chord_source": "detected",
        "chords": [chord(10), chord(12, "F", F), chord(14), chord(16, "F", F)],
        "strum": {"pattern": "D-DU-UDU", "accent": [0], "pattern_id": "p1", "confidence": 0.8},
    }
    base.update(section or {})
    return SongChartContent.model_validate(
        {"instrument": "electric", "bpm": bpm, "sections": [base], **extra}
    )


def test_cambio_de_acordes_usa_beats_desde_el_inicio_de_la_seccion():
    notation = build_section_exercise(content(), "verso", "chords").notation
    assert [(c.t, c.name) for c in notation.chords] == [(0, "Am"), (4, "F"), (8, "Am"), (12, "F")]
    assert notation.strum == []
    assert Notation.model_validate(notation.model_dump())


def test_bpm_sugerido_es_un_porcentaje_del_de_la_cancion():
    result = build_section_exercise(content(bpm=120), "verso", "chords")
    assert (result.bpm_start, result.bpm_target, result.notation.bpm) == (84, 120, 84)


def test_acordes_repetidos_seguidos_se_juntan():
    chords = [chord(10), chord(11), chord(12, "F", F)]
    result = build_section_exercise(content({"chords": chords}), "verso", "chords")
    assert [c.name for c in result.notation.chords] == ["Am", "F"]


def test_rasgueo_repite_el_patron_por_compas():
    strum = build_section_exercise(content(), "verso", "strumming").notation.strum
    assert [s.t for s in strum] == [0, 4, 8, 12, 16, 20, 24, 28]
    assert strum[0].pattern == "D-DU-UDU" and strum[0].accent == [0]


def test_usa_beats_por_ciclo_si_viene():
    section = {
        "strum": {"pattern": "DUDU", "beats_per_cycle": 2, "pattern_id": "p", "confidence": 0.5}
    }
    result = build_section_exercise(content(section), "verso", "strumming")
    assert result.notation.strum[1].t == 2


def test_con_beat_grid_convierte_con_la_grilla():
    grid = {"beats_s": [10 + 0.5 * i for i in range(40)], "downbeats_s": [10.0]}
    result = build_section_exercise(content(beat_grid=grid), "verso", "chords")
    assert [c.t for c in result.notation.chords] == [0, 4, 8, 12]


def test_el_ejercicio_se_acota_a_32_beats():
    section = {"end_s": 200, "chords": [chord(10), chord(100, "F", F)]}
    result = build_section_exercise(content(section), "verso", "chords")
    assert [c.name for c in result.notation.chords] == ["Am"]


def test_seccion_inexistente_en_el_chart():
    with pytest.raises(SectionNotFoundInChartError):
        build_section_exercise(content(), "puente", "chords")


def test_sin_acordes_no_se_puede():
    with pytest.raises(SectionNotPlayableError):
        build_section_exercise(content({"chords": []}), "verso", "chords")


def test_rasgueo_sin_patron_no_se_puede():
    with pytest.raises(SectionNotPlayableError):
        build_section_exercise(content({"strum": None}), "verso", "strumming")


def test_el_largo_se_redondea_hacia_arriba_a_ciclos_completos():
    section = {
        "end_s": 20,
        "chords": [chord(10), chord(19, "F", F)],
        "strum": {"pattern": "DU", "beats_per_cycle": 8, "pattern_id": "p", "confidence": 0.5},
    }
    result = build_section_exercise(content(section), "verso", "strumming")
    assert [s.t for s in result.notation.strum] == [0, 8, 16]
    assert [c.name for c in result.notation.chords] == ["Am", "F"]


def test_el_redondeo_respeta_el_tope_de_32_beats():
    section = {
        "end_s": 100,
        "strum": {"pattern": "DU", "beats_per_cycle": 6, "pattern_id": "p", "confidence": 0.5},
    }
    strum = build_section_exercise(content(section), "verso", "strumming").notation.strum
    assert [s.t for s in strum] == [0, 6, 12, 18, 24]


def test_en_tres_cuartos_el_ciclo_dura_tres_beats():
    section = {
        "end_s": 17,
        "strum": {"pattern": "D-DU", "pattern_id": "p", "confidence": 0.5},
    }
    result = build_section_exercise(content(section, time_signature="3/4"), "verso", "strumming")
    assert [s.t for s in result.notation.strum[:4]] == [0, 3, 6, 9]
    assert result.notation.time_signature == "3/4"


def test_el_origen_de_los_beats_es_el_inicio_de_la_seccion_igual_que_en_la_ui():
    # La UI (useBackingSync) cuenta desde section.start_s: si esto cambia se desalinea.
    chords = [chord(12), chord(14, "F", F)]
    result = build_section_exercise(content({"chords": chords}), "verso", "chords")
    assert [(c.t, c.name) for c in result.notation.chords] == [(4, "Am"), (8, "F")]
    assert min(e.t for e in result.notation.events) == 4


def test_seccion_de_menos_de_un_beat_da_un_ciclo():
    section = {"end_s": 10.2, "chords": [chord(10)]}
    result = build_section_exercise(content(section), "verso", "strumming")
    assert [s.t for s in result.notation.strum] == [0]
    assert [c.name for c in result.notation.chords] == ["Am"]


def test_acordes_como_notas_una_por_cuerda_que_suena():
    chords = [chord(10), chord(12, "F", F)]
    notation = build_section_exercise(content({"chords": chords}), "verso", "chords").notation
    first = [e for e in notation.events if e.t == 0]
    assert [(e.string, e.fret) for e in first] == [(5, 0), (4, 2), (3, 2), (2, 1), (1, 0)]
    assert all(e.dur == 4 for e in first)  # hasta el próximo acorde
    assert len([e for e in notation.events if e.t == 4]) == 6
    assert Notation.model_validate(notation.model_dump())


def test_rasgueo_repite_el_acorde_en_cada_golpe_y_el_guion_no_suena():
    chords = [chord(10), chord(12, "F", F)]
    section = {"chords": chords, "end_s": 14}
    notation = build_section_exercise(content(section), "verso", "strumming").notation
    times = sorted({e.t for e in notation.events})
    # 'D-DU-UDU' en 4 beats: celdas de 0,5 beats; el '-' (celdas 1 y 4) no suena
    assert times[:6] == [0, 1, 1.5, 2.5, 3, 3.5]
    assert {e.t for e in notation.events if e.t >= 4} == {4, 5, 5.5, 6.5, 7, 7.5}
    assert {e.fret for e in notation.events if e.t == 0 and e.string == 6} == set()
    assert {e.string for e in notation.events if e.t == 5} == {6, 5, 4, 3, 2, 1}


def test_seis_octavos_son_dos_beats_de_grilla_por_compas():
    section = {"strum": {"pattern": "DUDU", "pattern_id": "p", "confidence": 0.8}}
    result = build_section_exercise(content(section, time_signature="6/8"), "verso", "strumming")
    assert [s.t for s in result.notation.strum[:3]] == [0, 2, 4]


def test_ejercicio_guardado_sin_events_se_completa():
    legacy = {
        "bpm": 80,
        "chords": [{"t": 0, "name": "Am", "shape": AM}],
        "strum": [{"t": 0, "pattern": "DUDU"}, {"t": 4, "pattern": "DUDU"}],
    }
    done = complete_with_events(Notation.model_validate(legacy))
    assert len(done.events) == 5 * 4 * 2
    assert complete_with_events(done) == done


def _stored(section_id, notation):
    return {
        "id": 1,
        "lesson_id": None if section_id else 1,
        "song_section_id": section_id,
        "slug": "x",
        "title": "x",
        "type": "chords",
        "instrument": "electric",
        "category": "technique",
        "bpm_start": 60,
        "bpm_target": 80,
        "duration_min": 5,
        "description": None,
        "notation": notation,
    }


def test_al_leer_se_completan_los_ejercicios_de_cancion_sin_events():
    from guitarra_api.http.study_schemas import ExerciseOut

    legacy = {"bpm": 80, "chords": [{"t": 0, "name": "Am", "shape": AM}]}
    assert ExerciseOut.model_validate(_stored(5, legacy)).notation["events"]
    assert not ExerciseOut.model_validate(_stored(None, legacy)).notation.get("events")
