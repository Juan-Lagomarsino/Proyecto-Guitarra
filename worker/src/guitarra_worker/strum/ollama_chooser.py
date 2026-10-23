"""Elección de un patrón del catálogo con Ollama (modelo chico, salida JSON validada).

El LLM solo elige entre candidatos que ya filtraron las reglas: el prompt es corto, el pedido
lleva un JSON Schema con `enum` de ids y la respuesta se valida de nuevo acá (un modelo chico
puede ignorar el esquema). Cualquier falla (red, timeout, HTTP, JSON, id fuera de la lista) es
`ChooserError`; quien llama cae a las reglas. Nunca corre en el camino de audio en vivo.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from guitarra_worker.strum.catalog import Pattern


class ChooserError(Exception):
    """Ollama no respondió algo utilizable."""


@dataclass(frozen=True)
class SongContext:
    title: str
    artist: str
    bpm: float
    beats_per_bar: int


def build_prompt(candidates: Sequence[Pattern], context: SongContext) -> str:
    lines = [
        f"- {p.id}: {p.name}, estilo {p.style}, complejidad {p.complexity}/4, patrón {p.pattern}"
        for p in candidates
    ]
    return (
        "Sos un profesor de guitarra. Elegí el patrón más natural para esta canción.\n"
        f"Canción: {context.title} - {context.artist}. Tempo: {context.bpm:.0f} bpm, "
        f"compás de {context.beats_per_bar} tiempos.\n"
        "Patrones posibles (elegí exactamente uno, por su id):\n" + "\n".join(lines) + "\n"
        'Respondé solo un JSON: {"pattern_id": "<id>"}.'
    )


def _response_schema(candidates: Sequence[Pattern]) -> dict:
    return {
        "type": "object",
        "properties": {"pattern_id": {"type": "string", "enum": [p.id for p in candidates]}},
        "required": ["pattern_id"],
    }


class OllamaChooser:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = client or httpx.Client()

    def choose(self, candidates: Sequence[Pattern], context: SongContext) -> Pattern:
        content = self._ask(candidates, context)
        return self._validate(content, candidates)

    def _ask(self, candidates: Sequence[Pattern], context: SongContext) -> str:
        body = {
            "model": self._model,
            "stream": False,
            "format": _response_schema(candidates),
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": build_prompt(candidates, context)}],
        }
        try:
            response = self._client.post(
                f"{self._base_url}/api/chat", json=body, timeout=self._timeout_s
            )
            response.raise_for_status()
            return str(response.json()["message"]["content"])
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise ChooserError(f"Ollama no respondió bien: {error!r}") from error

    @staticmethod
    def _validate(content: str, candidates: Sequence[Pattern]) -> Pattern:
        try:
            chosen = json.loads(content)["pattern_id"]
        except (ValueError, KeyError, TypeError) as error:
            raise ChooserError(
                f"respuesta de Ollama no es el JSON esperado: {content!r}"
            ) from error
        for pattern in candidates:
            if pattern.id == chosen:
                return pattern
        raise ChooserError(f"Ollama eligió un id fuera de los candidatos: {chosen!r}")
