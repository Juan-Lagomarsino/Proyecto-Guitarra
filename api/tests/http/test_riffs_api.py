"""Riffs de la separación y mezcla por sección con la versión del usuario (F5-T06)."""

import copy

import pytest
import test_jobs_api as base
from sqlalchemy import select
from test_jobs_api import UI, chart_json, claim, new_song, post_result, result_body

from guitarra_api.infra.db.models import Correction, SongChart

# Fixtures reutilizadas de la API de la cola.
client, clock, jobs, songs = base.client, base.clock, base.jobs, base.songs

BPM = 100  # el de chart_content de test_songs_db


def riff(bpm=BPM, events=None):
    default = [{"t": 0, "dur": 1, "string": 3, "fret": 2, "confidence": 0.8}]
    return {"bpm": bpm, "events": default if events is None else events}


def other_riff():
    return riff(events=[{"t": 0, "dur": 2, "string": 2, "fret": 5}])


def chart_url(song_id):
    return f"/api/v1/songs/{song_id}/chart?instrument=electric"


def get_chart(client, song_id):
    return client.get(chart_url(song_id), headers=UI).json()


def first_fret(body, index=0):
    return body["content"]["sections"][index]["riff"]["events"][0]["fret"]


def charts(session, song_id):
    session.expire_all()
    return list(
        session.scalars(
            select(SongChart).where(SongChart.song_id == song_id).order_by(SongChart.version)
        )
    )


def analyzed_song(client, songs, jobs, ids=("intro",)):
    """Canción con el análisis hecho y la separación en cola."""
    song = new_song(songs)
    jobs.add_job(song.id)
    job = claim(client).json()
    body = result_body(ids=ids, charts=[chart_json("electric", ids)])
    assert post_result(client, job["job_id"], body).status_code == 200
    return song


def separate(client, riffs):
    sep = claim(client).json()
    assert sep["job_type"] == "separation"
    body = {"worker_id": "w1"} if riffs is None else {"worker_id": "w1", "riffs": riffs}
    response = post_result(client, sep["job_id"], body)
    assert response.status_code == 200, response.text


def another_separation(client, jobs, song):
    jobs.stage_separation(song.id)
    jobs._session.commit()
    return claim(client).json()["job_id"]


def user_edit(client, song_id, **changes):
    body = copy.deepcopy(get_chart(client, song_id)["content"])
    body["sections"][0].update(changes)
    response = client.put(chart_url(song_id), json=body, headers=UI)
    assert response.status_code == 200, response.text


def test_result_con_riffs_crea_version_auto_con_riffs(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    versions = charts(session, song.id)
    assert [(c.version, c.origin) for c in versions] == [(1, "auto"), (2, "auto")]
    assert versions[0].content["sections"][0]["riff"] is None
    assert versions[1].content["sections"][0]["riff"]["events"][0]["fret"] == 2
    body = get_chart(client, song.id)
    assert body["version"] == 2
    assert body["riff_sources"] == {"intro": "auto"}


def test_separacion_sin_riffs_no_cambia_los_charts(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, None)
    separate_empty = another_separation(client, jobs, song)
    assert post_result(client, separate_empty, {"worker_id": "w1", "riffs": {}}).status_code == 200
    assert len(charts(session, song.id)) == 1


def test_seccion_inexistente_se_ignora_y_la_separacion_termina(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"fantasma": riff()})
    assert len(charts(session, song.id)) == 1
    assert client.get(f"/api/v1/songs/{song.id}", headers=UI).json()["separation_status"] == "done"


def test_riff_invalido_se_descarta_y_el_resto_se_guarda(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs, ids=("intro", "verso"))
    invalid = riff(events=[{"t": 0, "dur": 1, "string": 9, "fret": 2}])
    separate(client, {"intro": invalid, "verso": riff()})
    latest = charts(session, song.id)[-1]
    riffs = {s["id"]: s["riff"] for s in latest.content["sections"]}
    assert riffs["intro"] is None
    assert riffs["verso"]["events"][0]["fret"] == 2


def test_riffs_que_no_sirven_se_descartan_sin_error(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs, ids=("a", "b", "c", "d"))
    bad = {
        "a": riff(bpm=120),  # bpm distinto del chart
        "b": riff(events=[]),  # vacío
        "c": riff(events=[{"t": 0, "dur": 100, "string": 3, "fret": 2}]),  # se pasa
        "d": "no es una notación",
    }
    separate(client, bad)
    assert len(charts(session, song.id)) == 1


def test_riffs_en_un_trabajo_de_analisis_dan_422(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    job = claim(client).json()
    body = {**result_body(), "riffs": {"intro": riff()}}
    assert post_result(client, job["job_id"], body).status_code == 422


def test_usuario_que_no_toco_riffs_ve_los_auto(client, songs, jobs):
    song = analyzed_song(client, songs, jobs)
    user_edit(client, song.id, name="Entrada")
    separate(client, {"intro": riff()})
    body = get_chart(client, song.id)
    assert body["origin"] == "user"
    assert body["content"]["sections"][0]["name"] == "Entrada"
    assert first_fret(body) == 2
    assert body["riff_sources"] == {"intro": "auto"}


def test_riff_corregido_por_el_usuario_gana_aunque_llegue_otro_auto(client, songs, jobs):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    user_edit(client, song.id, riff=other_riff())
    assert get_chart(client, song.id)["riff_sources"] == {"intro": "usuario"}
    job_id = another_separation(client, jobs, song)
    post_result(client, job_id, {"worker_id": "w1", "riffs": {"intro": riff()}})
    body = get_chart(client, song.id)
    assert first_fret(body) == 5
    assert body["riff_sources"] == {"intro": "usuario"}


def test_el_usuario_que_borra_el_riff_no_lo_ve_resucitar(client, songs, jobs):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    user_edit(client, song.id, riff=None)
    job_id = another_separation(client, jobs, song)
    post_result(client, job_id, {"worker_id": "w1", "riffs": {"intro": other_riff()}})
    body = get_chart(client, song.id)
    assert body["content"]["sections"][0]["riff"] is None
    assert body["riff_sources"] == {"intro": None}


def test_editar_solo_acordes_no_marca_el_riff_como_tocado(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    user_edit(client, song.id, name="Entrada")  # la UI devuelve el riff auto dentro del chart
    job_id = another_separation(client, jobs, song)
    post_result(client, job_id, {"worker_id": "w1", "riffs": {"intro": other_riff()}})
    body = get_chart(client, song.id)
    assert first_fret(body) == 5
    assert body["riff_sources"] == {"intro": "auto"}
    diffs = session.scalars(select(Correction.diff)).all()
    assert all("riff" not in d.get("sections", {}).get("intro", {}) for d in diffs)


def test_volver_a_la_automatica_olvida_lo_tocado(client, songs, jobs):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    user_edit(client, song.id, riff=other_riff())
    client.delete(f"/api/v1/songs/{song.id}/chart/user?instrument=electric", headers=UI)
    body = get_chart(client, song.id)
    assert (body["origin"], first_fret(body)) == ("auto", 2)
    user_edit(client, song.id, name="Otra")
    assert get_chart(client, song.id)["riff_sources"] == {"intro": "auto"}


def test_el_diff_de_correccion_incluye_el_riff(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    user_edit(client, song.id, riff=other_riff())
    change = session.scalars(select(Correction.diff)).all()[-1]["sections"]["intro"]["riff"]
    assert change["from"]["events"][0]["fret"] == 2
    assert change["to"]["events"][0]["fret"] == 5


def test_reanalisis_sin_riffs_arrastra_los_riffs_auto_previos(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff()})
    jobs.add_job(song.id)
    job = claim(client).json()
    assert job["job_type"] == "analyze"
    assert post_result(client, job["job_id"], result_body()).status_code == 200
    latest = charts(session, song.id)[-1]
    assert latest.version == 3
    assert latest.content["sections"][0]["riff"]["events"][0]["fret"] == 2
    assert get_chart(client, song.id)["riff_sources"] == {"intro": "auto"}


def test_reanalisis_no_arrastra_riffs_que_ya_no_caben(client, songs, jobs, session):
    song = analyzed_song(client, songs, jobs)
    separate(client, {"intro": riff(events=[{"t": 0, "dur": 14, "string": 3, "fret": 2}])})
    jobs.add_job(song.id)
    job = claim(client).json()
    slow = chart_json("electric") | {"bpm": 60}  # 10 s = 10 beats: ya no entran 14
    post_result(client, job["job_id"], result_body(charts=[slow]))
    assert charts(session, song.id)[-1].content["sections"][0]["riff"] is None


def test_chart_sin_riffs_informa_riff_sources_en_null(client, songs, jobs):
    song = analyzed_song(client, songs, jobs)
    assert get_chart(client, song.id)["riff_sources"] == {"intro": None}


def test_claim_de_separacion_trae_la_estructura_del_chart(client, songs, jobs):
    analyzed_song(client, songs, jobs, ids=("intro", "verso"))
    claimed = claim(client).json()
    assert claimed["job_type"] == "separation"
    chart = claimed["chart"]
    assert (chart["bpm"], chart["time_signature"], chart["capo"]) == (BPM, "4/4", 0)
    assert chart["beat_grid"] is None
    assert chart["sections"] == [
        {"id": "intro", "name": "Intro", "start_s": 0, "end_s": 10},
        {"id": "verso", "name": "Intro", "start_s": 10, "end_s": 20},
    ]


def test_claim_de_separacion_sin_chart_trae_chart_null(client, songs, jobs):
    song = new_song(songs)
    jobs.stage_separation(song.id)
    jobs._session.commit()
    claimed = claim(client).json()
    assert (claimed["job_type"], claimed["chart"]) == ("separation", None)


def test_claim_de_analisis_no_trae_chart(client, songs, jobs):
    jobs.add_job(new_song(songs).id)
    assert claim(client).json()["chart"] is None


def test_el_ejercicio_de_cancion_usa_la_vista_mezclada_con_riffs(
    client, songs, jobs, session, monkeypatch
):
    from guitarra_api.application import song_exercise_service as service

    song = analyzed_song(client, songs, jobs)
    user_edit(client, song.id, name="Entrada")
    separate(client, {"intro": riff()})
    section = song.sections[0]
    seen = {}

    def spy(content, section_id, kind):
        seen["riff"] = content.sections[0].riff
        raise RuntimeError("alcanza con ver el contenido")

    monkeypatch.setattr(service, "build_section_exercise", spy)
    with pytest.raises(RuntimeError):
        service.SongExerciseService(session).create(song.id, section.id, "chords", "electric")
    assert seen["riff"].events[0].fret == 2
