from pathlib import Path

from guitarra_worker.adapters.cifraclub import CifraClubChart, CifraClubSection
from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.cifraclub import CifraClubStep


class FakeClient:
    def __init__(self, chart=None, error=None):
        self.chart = chart
        self.error = error
        self.calls = []

    def fetch_chart(self, title, artist):
        self.calls.append((title, artist))
        if self.error:
            raise self.error
        return self.chart


def ctx(job, tmp_path: Path) -> PipelineContext:
    return PipelineContext(job=job, song_dir=tmp_path)


def test_con_datos(job, tmp_path):
    chart = CifraClubChart(
        url="u", key="G", capo=2, sections=[CifraClubSection("Intro", ["G", "D"])]
    )
    out = CifraClubStep(FakeClient(chart)).run(ctx(job, tmp_path))
    assert out == {
        "found": True,
        "url": "u",
        "key": "G",
        "capo": 2,
        "sections": [{"name": "Intro", "chords": ["G", "D"]}],
    }


def test_sin_datos_no_es_error(job, tmp_path):
    assert CifraClubStep(FakeClient(None)).run(ctx(job, tmp_path)) == {"found": False}


def test_cualquier_falla_inesperada_es_sin_datos(job, tmp_path):
    step = CifraClubStep(FakeClient(error=RuntimeError("boom")))
    assert step.run(ctx(job, tmp_path)) == {"found": False}


def test_intervalo_y_url_por_env(monkeypatch, tmp_path):
    from guitarra_worker.config import Settings

    monkeypatch.setenv("GUITAR_CIFRACLUB_MIN_INTERVAL_S", "5")
    monkeypatch.setenv("GUITAR_CIFRACLUB_BASE_URL", "https://otro.test")
    s = Settings(_env_file=tmp_path / "no-existe.env")
    assert s.cifraclub_min_interval_s == 5.0
    assert s.cifraclub_base_url == "https://otro.test"


def test_usa_titulo_y_artista_del_trabajo(job, tmp_path):
    client = FakeClient(None)
    CifraClubStep(client).run(ctx(job, tmp_path))
    assert client.calls == [("T", "A")]
