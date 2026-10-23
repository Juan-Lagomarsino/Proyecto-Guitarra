from guitarra_api.domain.chart_diff import diff_charts


def chart(**overrides):
    base = {
        "bpm": 96,
        "capo": 0,
        "sections": [
            {
                "id": "intro",
                "name": "Intro",
                "start_s": 0,
                "end_s": 10,
                "chords": [{"t_s": 1.0, "name": "Am"}],
                "strum": {"pattern_id": "rasgueo-4-balada"},
            },
            {"id": "verso", "name": "Verso", "start_s": 10, "end_s": 30, "chords": []},
        ],
    }
    return {**base, **overrides}


def test_charts_iguales_no_tienen_diff():
    assert diff_charts(chart(), chart()) == {}


def test_campo_de_nivel_superior_cambiado():
    assert diff_charts(chart(), chart(capo=2)) == {"capo": {"from": 0, "to": 2}}


def test_cambio_dentro_de_una_seccion_va_por_id_y_campo():
    new = chart()
    new["sections"][0]["name"] = "Entrada"
    new["sections"][1]["end_s"] = 28
    assert diff_charts(chart(), new) == {
        "sections": {
            "intro": {"name": {"from": "Intro", "to": "Entrada"}},
            "verso": {"end_s": {"from": 30, "to": 28}},
        }
    }


def test_acorde_y_rasgueo_cambiados():
    new = chart()
    new["sections"][0]["chords"] = [{"t_s": 1.0, "name": "Dm"}]
    new["sections"][0]["strum"] = {"pattern_id": "rasgueo-4-folk"}
    changes = diff_charts(chart(), new)["sections"]["intro"]
    assert changes["chords"] == {
        "from": [{"t_s": 1.0, "name": "Am"}],
        "to": [{"t_s": 1.0, "name": "Dm"}],
    }
    assert changes["strum"]["to"] == {"pattern_id": "rasgueo-4-folk"}


def test_secciones_agregadas_y_quitadas():
    new = chart()
    removed = new["sections"].pop(1)
    new["sections"].append({"id": "coro", "name": "Coro", "start_s": 30, "end_s": 50})
    diff = diff_charts(chart(), new)
    assert diff["sections_removed"] == [removed["id"]]
    assert diff["sections_added"] == ["coro"]
    assert "sections" not in diff
