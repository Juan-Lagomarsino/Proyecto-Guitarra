from validacion.metrica import (
    ciclo_minimo,
    cobertura,
    cobertura_vocabulario,
    coincide_vocabulario,
    flujo,
    mejor_referencia,
    normalizar,
)

G_CYCLE = flujo(["G", "B7", "Em", "C", "G", "D", "G", "D"])


def test_normaliza_enarmonicos_y_extensiones():
    assert normalizar("C#") == normalizar("Db") == (1, False)
    assert normalizar("Am7") == (9, True)
    assert normalizar("A/E") == (9, False)
    assert normalizar("Cmaj7") == (0, False)
    assert normalizar("N.C.") is None


def test_capo_suma_semitonos():
    assert normalizar("G", 2) == (9, False)


def test_flujo_quita_repetidos_e_ilegibles():
    assert flujo(["Am", "Am7", "N.C.", "G", "G"]) == [(9, True), (7, False)]


def test_ciclo_minimo():
    assert ciclo_minimo(flujo(["Am", "F", "Am", "F", "Am", "F"])) == flujo(["Am", "F"])
    assert ciclo_minimo(flujo(["Am", "F", "C"])) == flujo(["Am", "F", "C"])


def test_seccion_igual_al_ciclo_coincide():
    veredicto = mejor_referencia(G_CYCLE, [("Intro", G_CYCLE)])
    assert veredicto.coincide and veredicto.referencia == "Intro"


def test_seccion_con_otro_tono_no_coincide():
    otra = flujo(["A", "C#7", "F#m", "D", "A", "E", "A", "E"])
    assert not mejor_referencia(otra, [("Intro", G_CYCLE)]).coincide


def test_seccion_de_un_solo_acorde_no_prueba_nada():
    assert not mejor_referencia(flujo(["G"]), [("Intro", G_CYCLE)]).coincide


def test_seccion_corta_dentro_del_ciclo_coincide():
    assert mejor_referencia(flujo(["B7", "Em", "C"]), [("Intro", G_CYCLE)]).coincide


def test_acorde_ajeno_baja_la_pureza():
    sucia = flujo(["G", "F#", "A#", "C#", "G"])
    assert not mejor_referencia(sucia, [("Intro", G_CYCLE)]).coincide


def test_cobertura_de_la_referencia():
    assert cobertura(flujo(["Em", "G", "B7", "Em", "C", "G", "D"]), G_CYCLE)
    assert not cobertura(flujo(["A", "E", "F#m"]), G_CYCLE)


def test_vocabulario_de_cifra_plana():
    vocabulario = flujo(["A", "D", "F", "G", "E7"])
    assert coincide_vocabulario(flujo(["A", "D", "A", "D"]), vocabulario).coincide
    assert not coincide_vocabulario(flujo(["A", "Dm", "Am", "Dm"]), vocabulario).coincide
    assert not coincide_vocabulario(flujo(["A"]), vocabulario).coincide


def test_cobertura_del_vocabulario():
    vocabulario = flujo(["A", "D", "F", "G"])
    assert cobertura_vocabulario(flujo(["A", "D"]), vocabulario) == 0.5
