from pathlib import Path

from guitarra_worker.pipeline.step import PipelineContext
from guitarra_worker.steps.cifraclub import CifraClubStep

TEXT = "Tom: G\nCapo 2\n\n[Intro] G D\n\n[Verso]\nEm C\nletra de la canción\n"


def ctx(job, tmp_path: Path, cifra_text: str | None = None) -> PipelineContext:
    return PipelineContext(job=job.model_copy(update={"cifra_text": cifra_text}), song_dir=tmp_path)


def test_job_trae_cifra_text_opcional(job):
    assert job.cifra_text is None


def test_con_texto_parsea(job, tmp_path):
    out = CifraClubStep().run(ctx(job, tmp_path, TEXT))
    assert out == {
        "found": True,
        "url": "",
        "key": "G",
        "capo": 2,
        "sections": [
            {"name": "Intro", "chords": ["G", "D"]},
            {"name": "Verso", "chords": ["Em", "C"]},
        ],
    }


def test_sin_texto_es_sin_datos(job, tmp_path):
    assert CifraClubStep().run(ctx(job, tmp_path)) == {"found": False}


def test_texto_que_no_se_puede_parsear_es_sin_datos(job, tmp_path):
    assert CifraClubStep().run(ctx(job, tmp_path, "nada que ver acá")) == {"found": False}


def test_html_pegado_tambien_anda(job, tmp_path):
    out = CifraClubStep().run(ctx(job, tmp_path, "<pre>[Intro] <b>Am</b> <b>F</b></pre>"))
    assert out["found"] is True and out["sections"][0]["chords"] == ["Am", "F"]


def test_token_de_cache_cambia_con_el_texto(job):
    step = CifraClubStep()
    with_text = job.model_copy(update={"cifra_text": TEXT})
    other = job.model_copy(update={"cifra_text": TEXT + "\n[Puente] A"})
    assert step.cache_token(with_text) == step.cache_token(with_text)
    assert step.cache_token(with_text) != step.cache_token(other)
    assert step.cache_token(job) == ""
    assert step.cache_token(job.model_copy(update={"cifra_text": "  \n"})) == ""
