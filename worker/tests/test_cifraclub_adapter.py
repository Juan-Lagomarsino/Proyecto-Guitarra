import json
from pathlib import Path

import pytest

from guitarra_worker.adapters.cifraclub import parse_cifraclub_html, parse_cifraclub_text

JSON_DIR = Path(__file__).parent / "fixtures" / "cifraclub"
HTML_DIR = JSON_DIR / "html"
TEXT_DIR = JSON_DIR / "text"


def html(name: str) -> str:
    return (HTML_DIR / f"{name}.html").read_text(encoding="utf-8", errors="replace")


def text(name: str) -> str:
    return (TEXT_DIR / f"{name}.txt").read_text(encoding="utf-8")


def test_parsea_flaca():
    chart = parse_cifraclub_html(html("flaca"))
    assert chart is not None
    assert chart.sections[0].name == "Intro"
    assert chart.sections[0].chords[:4] == ["G", "B7", "Em", "C"]
    assert chart.capo == 0
    assert all(not s.name.lower().startswith("tab") for s in chart.sections)


def test_parsea_de_musica_ligera():
    chart = parse_cifraclub_html(html("de-musica-ligera"))
    assert chart is not None
    assert chart.sections[0].name == "Intro"
    assert chart.sections[0].chords == ["Bm", "G", "D", "A"] * 6
    assert len(chart.sections) > 2


def test_parsea_boys_dont_cry_con_sostenidos():
    chart = parse_cifraclub_html(html("boys-dont-cry"))
    assert chart is not None
    assert "C#m" in chart.sections[0].chords
    assert chart.all_chords()[:3] == ["A", "Bm", "C#m"]


def test_capo_y_tonalidad_de_los_spans():
    page = (
        '<span id="cifra_tom">tom: <a>Am</a></span>'
        '<span id="cifra_capo">Capotraste na 3ª casa</span>'
        "<pre>[Intro] <b>Am</b> <b>F</b></pre>"
    )
    chart = parse_cifraclub_html(page)
    assert chart is not None
    assert chart.capo == 3
    assert chart.key == "Am"


@pytest.mark.parametrize("page", ["", "<html>cambió todo</html>", "<pre>sin acordes</pre>"])
def test_html_irreconocible_da_none(page):
    assert parse_cifraclub_html(page) is None


def test_texto_plano_con_secciones_tom_y_capo():
    chart = parse_cifraclub_text(text("flaca"))
    assert chart is not None
    assert chart.key == "G"
    assert chart.capo == 2
    assert [s.name for s in chart.sections] == ["Intro", "Primeira Parte", "Refrão"]
    assert chart.sections[0].chords == ["G", "B7", "Em", "C", "G", "D", "G", "D"]
    assert chart.sections[1].chords == ["G", "B7", "Em", "C", "G", "D", "G"]
    assert chart.sections[2].chords == ["C", "G", "D", "Em"]


def test_texto_plano_ignora_tablatura_y_letra():
    chart = parse_cifraclub_text(text("flaca"))
    assert chart is not None
    assert all(not s.name.lower().startswith("tab") for s in chart.sections)
    assert "e" not in chart.all_chords()


def test_texto_sin_encabezados_va_a_una_seccion_sin_titulo():
    chart = parse_cifraclub_text(text("sin-secciones"))
    assert chart is not None
    assert len(chart.sections) == 1
    assert chart.sections[0].chords == ["Am", "G", "F", "E7"]
    assert chart.capo == 0 and chart.key is None


@pytest.mark.parametrize("raw", ["", "   \n\n", None])
def test_texto_vacio_da_none(raw):
    assert parse_cifraclub_text(raw) is None


def test_texto_basura_da_none():
    assert parse_cifraclub_text(text("basura")) is None


@pytest.mark.parametrize("line", ["Dado Ana Bebe", "Gato", "Dame la mano", "Ama", "Bebe"])
def test_palabras_comunes_no_son_acordes(line):
    assert parse_cifraclub_text(f"[Verso]\n{line}\n") is None


@pytest.mark.parametrize(
    "chord", ["C#m7", "Bb", "F#m7(b5)", "Cadd9", "Dsus4", "G/B", "Am7/G", "Ebmaj7", "A°", "E7(9)"]
)
def test_acordes_con_sufijos_se_reconocen(chord):
    chart = parse_cifraclub_text(f"[Verso]\n{chord}   Am\n")
    assert chart is not None
    assert chart.sections[0].chords == [chord, "Am"]


def test_barra_sin_bajo_se_toma_como_el_acorde_solo():
    chart = parse_cifraclub_text("[Verso]\nA/  D/  G/B  Em/\n")
    assert chart is not None
    assert chart.sections[0].chords == ["A", "D", "G/B", "Em"]


def test_capo_en_distintos_formatos():
    assert parse_cifraclub_text("Capo: 4\n[A]\nAm F\n").capo == 4
    assert parse_cifraclub_text("capotraste na 7ª casa\n[A]\nAm F\n").capo == 7
    assert parse_cifraclub_text("[A]\nAm F\n").capo == 0


def test_html_pegado_usa_el_parser_html():
    page = '<span id="cifra_capo">Capotraste na 3ª casa</span><pre>[Intro] <b>Am</b> <b>F</b></pre>'
    chart = parse_cifraclub_text(page)
    assert chart is not None
    assert chart.capo == 3 and chart.sections[0].chords == ["Am", "F"]


def render_as_text(fixture: dict) -> str:
    blocks = [
        (f"[{s['name']}]\n" if s["name"] else "") + "  ".join(s["chords"])
        for s in fixture["sections"]
    ]
    return f"Tom: {fixture['tonalidad']}\n\n" + "\n\n".join(blocks)


@pytest.mark.parametrize("name", ["flaca", "de-musica-ligera", "boys-dont-cry", "no-voy-en-tren"])
def test_texto_armado_desde_las_fixtures_da_las_mismas_secciones(name):
    fixture = json.loads((JSON_DIR / f"{name}.json").read_text(encoding="utf-8"))
    chart = parse_cifraclub_text(render_as_text(fixture))
    assert chart is not None
    assert [(s.name, s.chords) for s in chart.sections] == [
        (s["name"], s["chords"]) for s in fixture["sections"]
    ]
