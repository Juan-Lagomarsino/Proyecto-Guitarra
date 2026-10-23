"""Del runner al resultado para la API: pasos de datos fijos más Cifra Club y armado reales."""

import pytest

from chart_validation import validate_result
from guitarra_worker.pipeline.registry import assemble_result
from guitarra_worker.pipeline.runner import Heartbeat, run_pipeline
from guitarra_worker.steps.assemble import AssembleStep
from guitarra_worker.steps.cifraclub import CifraClubStep
from test_assemble_step import base_outputs

CIFRA = "[Intro] Am F C G\n\n[Verso]\nAm F C G Am F C G\n\n[Refrão]\nAm F C G Am F C G\n"


class CannedStep:
    version = "1"

    def __init__(self, name, output):
        self.name, self.output, self.runs = name, output, 0

    def run(self, ctx):
        self.runs += 1
        return self.output


def pipeline(job):
    outputs = base_outputs(job)
    canned = [CannedStep(n, outputs[n]) for n in outputs if n != "cifraclub"]
    steps = [*canned[:-1], CifraClubStep(), canned[-1]]
    return [*steps, AssembleStep()], canned


def run(steps, job, cache_dir):
    with Heartbeat(lambda step: None, 60) as heartbeat:
        return run_pipeline(steps, job, cache_dir, heartbeat, assemble_result)


@pytest.fixture
def with_cifra(job):
    return job.model_copy(update={"cifra_text": CIFRA})


def test_resultado_final_es_la_salida_del_armado_y_valida(job, tmp_path):
    steps, _ = pipeline(job)
    result = run(steps, job, tmp_path)
    assert set(result) == {"metadata", "sections", "charts"}
    validate_result(result)


def test_cifra_pegada_llega_al_chart(job, with_cifra, tmp_path):
    steps, _ = pipeline(job)
    result = run(steps, with_cifra, tmp_path)
    classical = next(c for c in result["charts"] if c["instrument"] == "classical")
    assert classical["sections"][0]["chord_source"] == "cifraclub"
    assert [s["name"] for s in result["sections"]] == ["Intro", "Verso", "Refrão"]
    validate_result(result)


def test_cambiar_la_cifra_rehace_el_armado_pero_no_los_pasos_previos(job, with_cifra, tmp_path):
    steps, canned = pipeline(job)
    first = run(steps, with_cifra, tmp_path)
    run(steps, with_cifra, tmp_path)
    assert all(step.runs == 1 for step in canned)

    changed = with_cifra.model_copy(update={"cifra_text": "[Puente]\nE B E B"})
    second = run(steps, changed, tmp_path)
    assert all(step.runs == 1 for step in canned[:-1])
    assert first != second
    assert [s["name"] for s in second["sections"]] == ["Parte A", "Parte B", "Parte C"]


def test_sin_cifra_el_pipeline_termina_igual(job, tmp_path):
    steps, _ = pipeline(job)
    assert run(steps, job, tmp_path)["charts"]
