"""Valida el resultado del armado contra el contrato de la API (`AnalysisResult`, ADR 0008).

El worker no importa la API en producción; los tests sí lo hacen, desde el árbol del repo, para
asegurar que lo que arma el worker lo acepta `POST /jobs/{id}/result`.
"""

import sys
from pathlib import Path
from typing import Any

API_SRC = Path(__file__).resolve().parents[2] / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))


def validate_result(result: dict[str, Any]):
    from guitarra_api.domain.analysis_result import AnalysisResult

    return AnalysisResult.model_validate(result)
