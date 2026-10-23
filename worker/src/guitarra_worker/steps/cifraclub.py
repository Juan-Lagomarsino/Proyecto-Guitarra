"""Paso de Cifra Club: parsea la cifra que Juan Pedro pegó a mano (ADR 0012).

'Sin datos' no es un error.

Entrada: `ctx.job.cifra_text` (texto plano o HTML de la página). No hace pedidos de red. Sin texto,
o si no se reconoce ningún acorde, devuelve `{"found": False}` y el pipeline sigue.

La alineación con lo detectado (domain/alignment.py) la hace el armado, que ve las salidas de este
paso y del de acordes. Si cambia el texto, `cache_token` invalida la caché de este paso y de los
siguientes.
"""

import hashlib
import logging
from typing import Any

from guitarra_worker.adapters.cifraclub import parse_cifraclub_text
from guitarra_worker.api_client import Job
from guitarra_worker.pipeline.step import PipelineContext

log = logging.getLogger(__name__)

NO_DATA: dict[str, Any] = {"found": False}
TOKEN_LENGTH = 12


class CifraClubStep:
    name = "cifraclub"
    version = "3"

    def cache_token(self, job: Job) -> str:
        """Hash del texto cargado; vacío si no hay texto (así sin cifra la clave no cambia)."""
        text = (job.cifra_text or "").strip()
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:TOKEN_LENGTH]

    def run(self, ctx: PipelineContext) -> dict[str, Any]:
        try:
            chart = parse_cifraclub_text(ctx.job.cifra_text)
        except Exception:
            log.exception("No pude leer la cifra cargada; sigo sin esos datos")
            return dict(NO_DATA)
        if chart is None:
            return dict(NO_DATA)
        return {
            "found": True,
            "url": chart.url,
            "key": chart.key,
            "capo": chart.capo,
            "sections": [{"name": s.name, "chords": s.chords} for s in chart.sections],
        }
