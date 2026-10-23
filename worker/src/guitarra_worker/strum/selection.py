"""Elección final: Ollama si responde algo válido, reglas si no. Nunca falla por el LLM."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from guitarra_worker.strum.catalog import Pattern
from guitarra_worker.strum.ollama_chooser import ChooserError, SongContext
from guitarra_worker.strum.rules import default_pattern

logger = logging.getLogger(__name__)

Source = Literal["ollama", "rules"]


class PatternChooser(Protocol):
    def choose(self, candidates: Sequence[Pattern], context: SongContext) -> Pattern: ...


@dataclass(frozen=True)
class Selection:
    pattern: Pattern
    source: Source


def select_pattern(
    candidates: Sequence[Pattern],
    context: SongContext,
    chooser: PatternChooser | None,
    density: float | None = None,
) -> Selection | None:
    if not candidates:
        return None
    if chooser is not None:
        try:
            return Selection(chooser.choose(candidates, context), "ollama")
        except ChooserError as error:
            logger.warning("Rasgueo: Ollama no sirvió (%s); uso las reglas", error)
    fallback = default_pattern(candidates, density)
    return Selection(fallback, "rules") if fallback else None
