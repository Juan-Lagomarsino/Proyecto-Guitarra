"""Riffs de un chart: validar los de la separación, arrastrarlos y mezclarlos por sección.

Regla (ADR 0018 y fase 5): la versión del usuario gana por sección, pero solo en el riff que el
usuario tocó. Si no lo tocó, se ve el riff de la última versión automática, aunque el resto de la
sección (acordes, rasgueo) venga de la edición del usuario.
"""

import copy
import logging
import math
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from guitarra_api.domain.notation import Notation
from guitarra_api.domain.song_chart import (
    RIFF_TOLERANCE_BEATS,
    BeatGrid,
    ChartSection,
    section_length_beats,
)

logger = logging.getLogger(__name__)

Json = dict[str, Any]
RiffSource = Literal["auto", "usuario"]


@dataclass(frozen=True)
class MergedChart:
    content: Json
    riff_sources: dict[str, RiffSource | None]  # por id de sección; None si no hay riff


def riff_sources_of(content: Json, source: RiffSource) -> dict[str, RiffSource | None]:
    return {s["id"]: (source if s.get("riff") else None) for s in content["sections"]}


def accept_riff(content: Json, section_id: str, raw: Any) -> Json | None:
    """El riff validado como JSON, o `None` (con log) si no sirve para esa sección del chart."""
    section = next((s for s in content["sections"] if s["id"] == section_id), None)
    if section is None:
        logger.warning("Riff ignorado: la sección '%s' no existe en el chart", section_id)
        return None
    try:
        riff = Notation.model_validate(raw)
    except ValidationError as error:
        logger.warning("Riff descartado en '%s': notación inválida (%s)", section_id, error)
        return None
    if not riff.events:
        logger.warning("Riff descartado en '%s': no tiene eventos", section_id)
        return None
    if not math.isclose(riff.bpm, content["bpm"], rel_tol=1e-6):
        logger.warning("Riff descartado en '%s': bpm %s distinto del chart", section_id, riff.bpm)
        return None
    if not riff_fits(content, section, riff):
        logger.warning("Riff descartado en '%s': se pasa del final de la sección", section_id)
        return None
    return riff.model_dump(mode="json", exclude_none=True)


def with_riffs(content: Json, riffs: dict[str, Json]) -> Json:
    """Copia del chart con esos riffs puestos en sus secciones."""
    result = copy.deepcopy(content)
    for section in result["sections"]:
        if section["id"] in riffs:
            section["riff"] = riffs[section["id"]]
    return result


def carry_over_riffs(previous: Json | None, new: Json) -> Json:
    """Chart nuevo con los riffs del anterior en las secciones que siguen y les caben.

    Un reanálisis no vuelve a correr la separación: sin esto se perderían riffs costosos.
    """
    if previous is None:
        return new
    old = {s["id"]: s["riff"] for s in previous["sections"] if s.get("riff")}
    kept = {
        section["id"]: old[section["id"]]
        for section in new["sections"]
        if section["id"] in old
        and not section.get("riff")
        and riff_fits(new, section, Notation.model_validate(old[section["id"]]))
    }
    return with_riffs(new, kept)


def merge_user_with_auto(user: Json, auto: Json, touched: set[str]) -> MergedChart:
    """Versión del usuario con el riff automático en las secciones donde no tocó el riff.

    Si la automática no tiene riff para la sección (o no cabe), queda el que guardó el usuario.
    """
    merged = copy.deepcopy(user)
    auto_riffs = {s["id"]: s.get("riff") for s in auto["sections"]}
    sources: dict[str, RiffSource | None] = {}
    for section in merged["sections"]:
        auto_riff = auto_riffs.get(section["id"])
        if (
            section["id"] not in touched
            and auto_riff
            and riff_fits(merged, section, Notation.model_validate(auto_riff))
        ):
            section["riff"] = auto_riff
            sources[section["id"]] = "auto"
        else:
            sources[section["id"]] = "usuario" if section.get("riff") else None
    return MergedChart(merged, sources)


def riff_fits(content: Json, section: Json, riff: Notation) -> bool:
    grid = BeatGrid.model_validate(content["beat_grid"]) if content.get("beat_grid") else None
    chart_section = ChartSection.model_validate({**section, "riff": None})
    limit = section_length_beats(chart_section, content["bpm"], grid) + RIFF_TOLERANCE_BEATS
    return all(event.t + event.dur <= limit for event in riff.events)
