from pathlib import Path

import httpx
import pytest

from guitarra_worker.adapters.cifraclub import (
    CifraClubClient,
    parse_cifraclub_html,
    slugify,
)

HTML_DIR = Path(__file__).parent / "fixtures" / "cifraclub" / "html"


def html(name: str) -> str:
    return (HTML_DIR / f"{name}.html").read_text(encoding="utf-8", errors="replace")


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


def test_slugify():
    assert slugify("Andrés Calamaro") == "andres-calamaro"
    assert slugify("Boys Don't Cry") == "boys-dont-cry"
    assert slugify("De Música Ligera!") == "de-musica-ligera"


class Clock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def make_client(handler, clock=None, interval=2.0):
    clock = clock or Clock()
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = CifraClubClient(
        http,
        base_url="https://cifra.test",
        min_interval_s=interval,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )
    return client, clock


def test_fetch_chart_arma_la_url_y_parsea():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=html("flaca"))

    client, _ = make_client(handler)
    chart = client.fetch_chart("Flaca", "Andrés Calamaro")
    assert seen == ["https://cifra.test/andres-calamaro/flaca/"]
    assert chart is not None and chart.url == seen[0]


@pytest.mark.parametrize("status", [403, 404, 500])
def test_error_http_da_none(status):
    client, _ = make_client(lambda r: httpx.Response(status))
    assert client.fetch_chart("x", "y") is None


def test_error_de_red_da_none():
    def handler(request):
        raise httpx.ConnectError("sin red")

    client, _ = make_client(handler)
    assert client.fetch_chart("x", "y") is None


def test_sin_titulo_o_artista_no_pide_nada():
    def handler(request):
        raise AssertionError("no debería haber pedido")

    client, _ = make_client(handler)
    assert client.fetch_chart(None, "y") is None
    assert client.fetch_chart("x", "") is None


def test_respeta_el_intervalo_entre_pedidos():
    client, clock = make_client(lambda r: httpx.Response(404), interval=2.0)
    client.fetch_chart("a", "b")
    assert clock.sleeps == []
    clock.now += 0.5
    client.fetch_chart("c", "d")
    assert clock.sleeps == [pytest.approx(1.5)]
    clock.now += 5
    client.fetch_chart("e", "f")
    assert len(clock.sleeps) == 1
