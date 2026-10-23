from pathlib import Path

from guitarra_worker.adapters.cifraclub import parse_cifraclub_text
from guitarra_worker.domain.alignment import transpose_chord as rename
from guitarra_worker.domain.chart_assembly import (
    SectionDraft,
    match_with_cifra,
    merge_detected,
    plan_sections,
)
from guitarra_worker.domain.section_alignment import match_sections, minimal_cycle

SPAN_S = 2.0
FLACA_SHORT = Path(__file__).parent / "fixtures" / "cifraclub" / "text" / "flaca.txt"

VERSE = ["G", "D", "Em", "C"]
CHORUS = ["C", "G", "D", "Em"]


def detected_from(sections):
    """Un acorde cada 2 s; `sections` es una lista de listas de nombres."""
    spans, drafts, t = [], [], 0.0
    for labels in sections:
        start = t
        for label in labels:
            spans.append({"start": t, "end": t + SPAN_S, "label": label, "confidence": 0.7})
            t += SPAN_S
        drafts.append(SectionDraft(start, t, None, None))
    return merge_detected(spans), drafts


def cifra(*sections, capo=0):
    return {
        "found": True,
        "capo": capo,
        "sections": [{"name": n, "chords": c} for n, c in sections],
    }


def sources(detected, drafts, match):
    return [p.chord_source for p in plan_sections(drafts, detected, match)]


def names(detected, drafts, match):
    return [p.name for p in plan_sections(drafts, detected, match)]


def test_ciclo_minimo():
    assert minimal_cycle(["G", "D", "G", "D", "G", "D"]) == ["G", "D"]
    assert minimal_cycle(["G", "D", "G", "D", "G"]) == ["G", "D"]
    assert minimal_cycle(["G", "B7", "Em", "C"]) == ["G", "B7", "Em", "C"]
    assert minimal_cycle([]) == []


def test_cifra_corta_de_flaca_se_usa_por_seccion():
    chart = parse_cifraclub_text(FLACA_SHORT.read_text(encoding="utf-8"))
    short = {
        "found": True,
        "capo": 0,
        "sections": [{"name": s.name, "chords": s.chords} for s in chart.sections],
    }
    intro = ["G", "B7", "Em", "C", "G", "D", "G", "D"]
    verse = ["G", "B7", "Em", "C", "G", "D", "G"]
    # La detección repite la progresión; el cierre es otra cosa que la cifra no tiene.
    detected, drafts = detected_from(
        [intro, verse * 2, ["C", "G", "D", "Em", "C", "G", "D", "Em"], ["F#", "A#", "F#"]]
    )
    match = match_with_cifra(short, detected, drafts)
    assert match is not None
    assert sources(detected, drafts, match) == ["cifraclub"] * 3 + ["detected"]
    assert names(detected, drafts, match)[0] == "Intro"
    assert names(detected, drafts, match)[2] == "Refrão"


def test_sin_secciones_la_cifra_corta_no_alinea():
    detected, drafts = detected_from([VERSE * 4, CHORUS * 4])
    short = cifra(("Verso", VERSE), ("Coro", CHORUS))
    assert match_with_cifra(short, detected) is None
    assert match_with_cifra(short, detected, drafts) is not None


def test_cifra_completa_sigue_alineando_global():
    detected, drafts = detected_from([VERSE * 3, CHORUS * 3])
    full = cifra(("Verso", VERSE * 3), ("Coro", CHORUS * 3))
    match = match_with_cifra(full, detected, drafts)
    assert match is not None
    assert names(detected, drafts, match) == ["Verso", "Coro"]
    assert sources(detected, drafts, match) == ["cifraclub"] * 2


def test_cifra_sin_relacion_no_se_usa():
    detected, drafts = detected_from([VERSE * 4, CHORUS * 4])
    other = cifra(("Verso", ["F#m", "Bb", "Ab", "Eb"]), ("Coro", ["Db", "Gb", "Cm"]))
    assert match_with_cifra(other, detected, drafts) is None


def test_secciones_repetidas_usan_la_misma_cifra():
    detected, drafts = detected_from([VERSE * 2, CHORUS * 2, VERSE * 2, CHORUS * 2])
    short = cifra(("Verso", VERSE), ("Coro", CHORUS))
    match = match_with_cifra(short, detected, drafts)
    assert names(detected, drafts, match) == ["Verso", "Coro", "Verso", "Coro"]
    assert sources(detected, drafts, match) == ["cifraclub"] * 4


def test_misma_progresion_en_dos_secciones_reparte_los_nombres_en_orden():
    detected, drafts = detected_from([VERSE * 2, VERSE * 2])
    match = match_with_cifra(cifra(("Intro", VERSE), ("Verso", VERSE)), detected, drafts)
    assert names(detected, drafts, match) == ["Intro", "Verso"]


def test_transposicion_coherente_con_el_capo():
    # La cifra dice G D Em C con capo 2: suena A E F#m D.
    sounding = ["A", "E", "F#m", "D"]
    detected, drafts = detected_from([sounding * 2, sounding * 2])
    match = match_with_cifra(cifra(("Verso", VERSE), capo=2), detected, drafts)
    assert match is not None
    chords = [c.name for p in plan_sections(drafts, detected, match) for c in p.chords]
    assert chords[:4] == ["A", "E", "F#m", "D"]
    assert sources(detected, drafts, match) == ["cifraclub"] * 2


def test_la_seccion_que_no_coincide_queda_detectada():
    detected, drafts = detected_from([VERSE * 3, ["Am", "F", "Dm", "Bb", "Gm"]])
    match = match_with_cifra(cifra(("Verso", VERSE)), detected, drafts)
    assert sources(detected, drafts, match) == ["cifraclub", "detected"]


def test_seccion_de_la_cifra_sin_nombre_global_usa_el_nombre_por_defecto():
    detected, drafts = detected_from([VERSE * 3])
    match = match_with_cifra(cifra(("", VERSE * 3)), detected, drafts)
    assert sources(detected, drafts, match) == ["cifraclub"]
    assert names(detected, drafts, match) == ["Sección 1"]


def test_seccion_de_la_cifra_sin_nombre_por_seccion_usa_el_nombre_por_defecto():
    detected, drafts = detected_from([VERSE * 3, CHORUS * 3])
    match = match_with_cifra(cifra(("", VERSE)), detected, drafts)
    assert sources(detected, drafts, match)[0] == "cifraclub"
    assert names(detected, drafts, match)[0] == "Sección 1"


def test_ciclo_mas_largo_que_la_seccion_detectada():
    long_cycle = ["G", "B7", "Em", "C", "G", "D", "G", "D"]
    sections = match_sections([("Intro", long_cycle)], [["G", "B7", "Em", "C"]], 0, rename)
    assert sections[0] is not None
    assert [name for _, name in sections[0].chords] == ["G", "B7", "Em", "C"]


def test_ciclo_mas_largo_con_la_seccion_a_mitad_del_ciclo_no_coincide():
    long_cycle = ["G", "B7", "Em", "C", "G", "D", "G", "D"]
    assert match_sections([("Intro", long_cycle)], [["F#", "Bb", "Ab"]], 0, rename) == [None]
