from guitarra_core.chord_preferences import (
    EMA_ALPHA,
    ChordShapePreferences,
    ShapeChoice,
    canonical_chord_name,
    chosen_shapes,
    shape_key,
)


def chart(*chords, capo=0, section="verse"):
    return {
        "capo": capo,
        "sections": [
            {
                "id": section,
                "chords": [{"t_s": t, "name": name, "shape": shape} for t, name, shape in chords],
            }
        ],
    }


G_OPEN = [3, 2, 0, 0, 0, 3]
G_BARRE = [3, 5, 5, 4, 3, 3]


def test_shape_key_es_absoluta_y_marca_cuerdas_mudas():
    assert shape_key(["x", 3, 2, 0, 1, 0], capo=0) == "x,3,2,0,1,0"
    assert shape_key(["x", 3, 2, 0, 1, 0], capo=2) == "x,5,4,2,3,2"


def test_nombre_canonico_unifica_alias_y_descarta_sin_acorde():
    assert canonical_chord_name("A:min") == canonical_chord_name("Am") == "Am"
    assert canonical_chord_name("N") is None
    assert canonical_chord_name("???") is None


def test_cambio_de_forma_del_mismo_acorde_es_preferencia():
    auto = chart((0.0, "G", G_OPEN))
    user = chart((0.0, "G", G_BARRE))
    assert chosen_shapes(auto, user) == [ShapeChoice("G", shape_key(G_BARRE, 0))]


def test_cambio_de_nombre_no_es_preferencia_de_forma():
    auto = chart((0.0, "G", G_OPEN))
    user = chart((0.0, "Em", [0, 2, 2, 0, 0, 0]))
    assert chosen_shapes(auto, user) == []


def test_sin_cambios_o_en_otro_momento_no_cuenta():
    auto = chart((0.0, "G", G_OPEN), (2.0, "C", ["x", 3, 2, 0, 1, 0]))
    assert chosen_shapes(auto, auto) == []
    moved = chart((0.0, "G", G_OPEN), (2.5, "C", ["x", 3, 5, 5, 5, 3]))
    assert chosen_shapes(auto, moved) == []


def test_alias_del_nombre_cuenta_como_el_mismo_acorde():
    auto = chart((0.0, "Am", ["x", 0, 2, 2, 1, 0]))
    user = chart((0.0, "A:min", [5, 7, 7, 5, 5, 5]))
    assert [c.chord for c in chosen_shapes(auto, user)] == ["Am"]


def test_misma_forma_real_con_otro_capo_da_la_misma_clave():
    # A con capo 2 tocando la forma de G abierto == la misma forma escrita en altura absoluta
    with_capo = chart((0.0, "A", G_OPEN), capo=2)
    absolute = chart((0.0, "A", [5, 4, 2, 2, 2, 5]), capo=0)
    assert chosen_shapes(with_capo, absolute) == []
    assert shape_key(G_OPEN, capo=2) == shape_key([5, 4, 2, 2, 2, 5], capo=0)


def test_cambio_de_forma_con_capo_guarda_la_forma_en_altura_absoluta():
    auto = chart((0.0, "A", G_OPEN), capo=2)
    user = chart((0.0, "A", ["x", 0, 2, 2, 2, 0]), capo=2)
    assert chosen_shapes(auto, user) == [ShapeChoice("A", "x,2,4,4,4,2")]


def test_secciones_nuevas_o_sin_acordes_se_ignoran():
    auto = chart((0.0, "G", G_OPEN))
    user = chart((0.0, "G", G_BARRE), section="otra")
    assert chosen_shapes(auto, user) == []


def test_aprender_suma_y_acumula_con_ema():
    prefs = ChordShapePreferences().learn("electric", [ShapeChoice("G", "a")])
    assert prefs.weights["electric"]["G"] == {"a": EMA_ALPHA}
    prefs = prefs.learn("electric", [ShapeChoice("G", "a")])
    expected = EMA_ALPHA * (1 - EMA_ALPHA) + EMA_ALPHA
    assert abs(prefs.weights["electric"]["G"]["a"] - expected) < 1e-9


def test_otra_eleccion_baja_la_anterior_y_poda_lo_irrelevante():
    prefs = ChordShapePreferences().learn("electric", [ShapeChoice("G", "a")])
    prefs = prefs.learn("electric", [ShapeChoice("G", "b")])
    weights = prefs.weights["electric"]["G"]
    assert weights["a"] < EMA_ALPHA
    assert weights["b"] == EMA_ALPHA
    for _ in range(40):
        prefs = prefs.learn("electric", [ShapeChoice("G", "b")])
    assert "a" not in prefs.weights["electric"]["G"]
    assert prefs.weights["electric"]["G"]["b"] <= 1.0


def test_un_acorde_no_afecta_a_otro_ni_a_otro_instrumento():
    prefs = ChordShapePreferences().learn("electric", [ShapeChoice("G", "a")])
    prefs = prefs.learn("electric", [ShapeChoice("C", "c")])
    assert prefs.weights["electric"]["G"] == {"a": EMA_ALPHA}
    assert "classical" not in prefs.weights


def test_json_ida_y_vuelta():
    prefs = ChordShapePreferences().learn("electric", [ShapeChoice("G", "a")])
    assert prefs.to_json() == {"electric": {"G": {"a": EMA_ALPHA}}}
    assert ChordShapePreferences.from_json(prefs.to_json()) == prefs
    assert ChordShapePreferences.from_json(None) == ChordShapePreferences()
