from pathlib import Path

import pytest

from chart_validation import validate_result
from guitarra_worker.pipeline.step import PermanentStepError, PipelineContext
from guitarra_worker.steps.assemble import AssembleStep
from guitarra_worker.steps.strum import StrumStep

DETECTED_CYCLE = ["Am7", "F", "C", "G"]
CIFRA_CYCLE = ["Am", "F", "C", "G"]
SONG_END_S = 40.0


def tempo_output():
    beats = [i * 0.5 for i in range(int(SONG_END_S / 0.5) + 1)]
    return {
        "bpm": 120.0,
        "beats_per_bar": 4,
        "beats": beats,
        "downbeats": beats[::4],
        "first_beat_s": 0.0,
        "first_downbeat_s": 0.0,
    }


def structure_output(names=(None, None, None)):
    bounds = [(0.0, 8.0, "A"), (8.0, 24.0, "B"), (24.0, 40.0, "C")]
    return {
        "sections": [
            {
                "order": i,
                "start_s": s,
                "end_s": e,
                "start_bar": 0,
                "end_bar": 0,
                "group": g,
                "name": names[i],
            }
            for i, (s, e, g) in enumerate(bounds)
        ],
        "confidence": "media",
    }


def chords_output(cycle=DETECTED_CYCLE, confidence=0.8):
    spans = [
        {
            "start": 2.0 * i,
            "end": 2.0 * i + 2.0,
            "label": cycle[i % len(cycle)],
            "confidence": confidence,
        }
        for i in range(int(SONG_END_S / 2))
    ]
    return {"model": "btc", "chords": spans}


KEY = {"key": {"tonic": "A", "mode": "minor", "name": "Am", "relative": "C", "confidence": 0.7}}


def cifra_output(cycle=CIFRA_CYCLE, capo=0):
    names = [cycle[i % len(cycle)] for i in range(20)]
    return {
        "found": True,
        "url": "",
        "key": "Am",
        "capo": capo,
        "sections": [
            {"name": "Intro", "chords": names[:4]},
            {"name": "Verso", "chords": names[4:12]},
            {"name": "Refrão", "chords": names[12:]},
        ],
    }


def base_outputs(job):
    tempo = tempo_output()
    strum = StrumStep(None).run(
        PipelineContext(job=job, song_dir=Path("."), outputs={"tempo": tempo})
    )
    return {
        "source": {"youtube_id": "abc123", "title": "Yt T", "artist": "Yt A", "year": 1990},
        "download": {"duration_s": SONG_END_S, "wav_path": "x.wav"},
        "tempo": tempo,
        "structure": structure_output(),
        "chords": chords_output(),
        "key": KEY,
        "cifraclub": {"found": False},
        "strum": strum,
    }


def assemble(job, tmp_path, outputs, versions=None):
    ctx = PipelineContext(job=job, song_dir=tmp_path, outputs=outputs)
    return AssembleStep(versions).run(ctx)


def chart_of(result, instrument):
    return next(c for c in result["charts"] if c["instrument"] == instrument)


def test_resultado_valida_contra_el_contrato_de_la_api(job, tmp_path):
    result = assemble(job, tmp_path, base_outputs(job))
    parsed = validate_result(result)
    assert [c.instrument for c in parsed.charts] == ["classical", "electric"]


def test_cabecera_con_tonalidad_bpm_y_compas(job, tmp_path):
    result = assemble(job, tmp_path, base_outputs(job))
    chart = chart_of(result, "electric")
    assert chart["bpm"] == 120.0 and chart["time_signature"] == "4/4"
    assert chart["key"] == {"tonic": "A", "mode": "minor", "confidence": 0.7}
    assert chart["beat_grid"]["beats_s"][:3] == [0.0, 0.5, 1.0]
    assert result["metadata"] == {
        "bpm": 120.0,
        "key": "Am",
        "duration_s": SONG_END_S,
        "year": 1990,
        "youtube_id": "abc123",
    }


def test_titulo_y_artista_solo_si_el_trabajo_no_los_tiene(job, tmp_path):
    result = assemble(
        job.model_copy(update={"title": None, "artist": None}), tmp_path, base_outputs(job)
    )
    assert result["metadata"]["title"] == "Yt T" and result["metadata"]["artist"] == "Yt A"


def test_nombres_por_defecto_desde_el_grupo_e_ids_unicos(job, tmp_path):
    result = assemble(job, tmp_path, base_outputs(job))
    assert [s["name"] for s in result["sections"]] == ["Parte A", "Parte B", "Parte C"]
    assert [s["slug"] for s in result["sections"]] == ["01-parte-a", "02-parte-b", "03-parte-c"]
    assert [s["position"] for s in result["sections"]] == [0, 1, 2]


def test_nombre_de_la_estructura_se_respeta_sin_cifra(job, tmp_path):
    outputs = base_outputs(job)
    outputs["structure"] = structure_output(("Intro", "Estrofa", None))
    names = [s["name"] for s in assemble(job, tmp_path, outputs)["sections"]]
    assert names == ["Intro", "Estrofa", "Parte C"]


def test_acordes_detectados_van_a_su_seccion_con_forma(job, tmp_path):
    chart = chart_of(assemble(job, tmp_path, base_outputs(job)), "electric")
    intro = chart["sections"][0]
    assert intro["chord_source"] == "detected"
    assert [c["t_s"] for c in intro["chords"]] == [0.0, 2.0, 4.0, 6.0]
    assert [c["name"] for c in intro["chords"]] == ["Am7", "F", "C", "G"]
    assert all(len(c["shape"]) == 6 for c in intro["chords"])


def test_con_cifra_buena_usa_sus_nombres_con_tiempos_detectados(job, tmp_path):
    outputs = base_outputs(job)
    outputs["cifraclub"] = cifra_output()
    chart = chart_of(assemble(job, tmp_path, outputs), "electric")
    intro = chart["sections"][0]
    assert [c["name"] for c in intro["chords"]] == ["Am", "F", "C", "G"]
    assert [c["t_s"] for c in intro["chords"]] == [0.0, 2.0, 4.0, 6.0]
    assert intro["chord_source"] == "cifraclub"
    assert all(c["confidence"] > 0.8 for c in intro["chords"])
    assert {"step": "cifraclub", "tool": "cifraclub-texto", "version": "1"} in chart["sources"]


def test_con_cifra_buena_los_nombres_de_seccion_son_los_de_la_cifra(job, tmp_path):
    outputs = base_outputs(job)
    outputs["cifraclub"] = cifra_output()
    names = [s["name"] for s in assemble(job, tmp_path, outputs)["sections"]]
    assert names == ["Intro", "Verso", "Refrão"]


def test_con_cifra_transpuesta_usa_los_nombres_transpuestos(job, tmp_path):
    outputs = base_outputs(job)
    outputs["chords"] = chords_output(["Bm", "G", "D", "A"])
    outputs["cifraclub"] = cifra_output(["Am", "F", "C", "G"], capo=2)
    chart = chart_of(assemble(job, tmp_path, outputs), "classical")
    intro = chart["sections"][0]
    assert [c["name"] for c in intro["chords"]] == ["Bm", "G", "D", "A"]
    assert intro["chord_source"] == "cifraclub"
    assert chart["capo"] == 2


def test_con_cifra_que_no_alinea_se_ignora(job, tmp_path):
    outputs = base_outputs(job)
    outputs["cifraclub"] = {
        "found": True,
        "url": "",
        "key": None,
        "capo": 11,
        "sections": [{"name": "X", "chords": ["Bbdim", "Ebdim"]}],
    }
    result = assemble(job, tmp_path, outputs)
    chart = chart_of(result, "classical")
    assert chart["sections"][0]["chord_source"] == "detected"
    assert [s["name"] for s in result["sections"]] == ["Parte A", "Parte B", "Parte C"]
    assert "cifraclub" not in {s["step"] for s in chart["sources"]}
    assert chart["capo"] <= 7  # el capo de la cifra (11) no se usa: sugiere el core
    validate_result(result)


def test_seccion_sin_acordes_es_valida(job, tmp_path):
    outputs = base_outputs(job)
    outputs["chords"] = {
        "model": "btc",
        "chords": [c for c in chords_output()["chords"] if c["start"] >= 8.0],
    }
    result = assemble(job, tmp_path, outputs)
    assert chart_of(result, "classical")["sections"][0]["chords"] == []
    validate_result(result)


def test_acordes_sin_acorde_N_se_omiten(job, tmp_path):
    outputs = base_outputs(job)
    outputs["chords"]["chords"][1]["label"] = "N"
    intro = chart_of(assemble(job, tmp_path, outputs), "electric")["sections"][0]
    assert [c["t_s"] for c in intro["chords"]] == [0.0, 4.0, 6.0]


def test_tonalidad_none_no_pone_key(job, tmp_path):
    outputs = base_outputs(job)
    outputs["key"] = {"key": None}
    result = assemble(job, tmp_path, outputs)
    assert "key" not in chart_of(result, "classical")
    assert "key" not in result["metadata"]
    validate_result(result)


def test_cancion_sin_secciones_da_una_sola(job, tmp_path):
    outputs = base_outputs(job)
    outputs["structure"] = {"sections": [], "confidence": "baja"}
    result = assemble(job, tmp_path, outputs)
    assert [(s["name"], s["start_s"], s["end_s"]) for s in result["sections"]] == [
        ("Canción", 0.0, SONG_END_S)
    ]
    assert len(chart_of(result, "electric")["sections"][0]["chords"]) == 20
    validate_result(result)


def test_sin_tempo_es_error_permanente(job, tmp_path):
    outputs = base_outputs(job)
    outputs["tempo"] = {"bpm": None, "beats_per_bar": None, "beats": [], "downbeats": []}
    with pytest.raises(PermanentStepError):
        assemble(job, tmp_path, outputs)


def test_arpegio_solo_en_clasica_y_rasgueo_en_todas_las_secciones(job, tmp_path):
    result = assemble(job, tmp_path, base_outputs(job))
    classical, electric = chart_of(result, "classical"), chart_of(result, "electric")
    assert all(s["strum"] and s["arpeggio"] for s in classical["sections"])
    assert all(s["strum"] and "arpeggio" not in s for s in electric["sections"])
    assert len({s["strum"]["pattern_id"] for s in classical["sections"]}) == 1


def test_sin_rasgueo_las_secciones_quedan_sin_patron(job, tmp_path):
    outputs = base_outputs(job)
    outputs["strum"] = {"strum": None, "arpeggio": None}
    result = assemble(job, tmp_path, outputs)
    assert all("strum" not in s for s in chart_of(result, "classical")["sections"])
    validate_result(result)


def test_capo_clasica_viene_del_core_y_electrica_es_cero(job, tmp_path):
    outputs = base_outputs(job)
    outputs["chords"] = chords_output(["F#m", "D", "A", "E"])
    result = assemble(job, tmp_path, outputs)
    assert chart_of(result, "electric")["capo"] == 0
    assert chart_of(result, "classical")["capo"] >= 0
    validate_result(result)


def test_fuentes_con_la_version_de_cada_paso(job, tmp_path):
    versions = {"tempo": "3", "chords": "2"}
    sources = chart_of(assemble(job, tmp_path, base_outputs(job), versions), "classical")["sources"]
    by_step = {s["step"]: s for s in sources}
    assert by_step["tempo"]["version"] == "3" and by_step["chords"]["version"] == "2"
    assert by_step["chords"]["tool"] == "btc"
    assert "cifraclub" not in by_step


G_BARRE_ABSOLUTE = "3,5,5,4,3,3"


def chord_named(result, instrument, name):
    chart = chart_of(result, instrument)
    return next(c for s in chart["sections"] for c in s["chords"] if c["name"] == name)


def test_sin_preferencias_la_forma_es_la_de_siempre(job, tmp_path):
    base = assemble(job, tmp_path, base_outputs(job))
    empty = job.model_copy(update={"chord_shape_preferences": {}})
    assert assemble(empty, tmp_path, base_outputs(job)) == base


def test_con_preferencia_usa_la_forma_preferida(job, tmp_path):
    prefs = {"electric": {"G": {G_BARRE_ABSOLUTE: 0.6}}}
    preferring = job.model_copy(update={"chord_shape_preferences": prefs})
    result = assemble(preferring, tmp_path, base_outputs(job))
    assert chord_named(result, "electric", "G")["shape"] == [3, 5, 5, 4, 3, 3]
    assert chord_named(result, "electric", "G")["barre"] is not None
    base = assemble(job, tmp_path, base_outputs(job))
    assert chord_named(result, "classical", "G") == chord_named(base, "classical", "G")
    validate_result(result)


def test_la_preferencia_invalida_la_cache_del_paso(job):
    prefs = {"electric": {"G": {G_BARRE_ABSOLUTE: 1}}}
    other = job.model_copy(update={"chord_shape_preferences": prefs})
    step = AssembleStep()
    assert step.cache_token(job) == ""
    assert step.cache_token(other) != ""
