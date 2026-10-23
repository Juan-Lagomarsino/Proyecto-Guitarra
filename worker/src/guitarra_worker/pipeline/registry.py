"""Lista ordenada de pasos del pipeline. T06 a T13 suman los reales acá."""

from typing import Any

from guitarra_worker.pipeline.step import PipelineContext, Step


class NoopStep:
    """Paso de ejemplo: devuelve un resultado vacío con la forma que espera la API."""

    name = "noop"
    version = "1"

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        return {"metadata": {}, "sections": [], "charts": []}


def assemble_result(outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Arma el cuerpo del result (`metadata`, `sections`, `charts`) con las salidas de los pasos.

    T13 lo reemplaza para leer la salida del paso de armado.
    """
    return outputs["noop"]


def default_steps() -> list[Step]:
    return [NoopStep()]
