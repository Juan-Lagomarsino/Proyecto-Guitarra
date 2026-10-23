"""Diferencia entre dos versiones del contenido de un chart (insumo del historial de correcciones).

Forma del resultado, vacío si no cambió nada:
`{campo: {from, to}, "sections": {id: {campo: {from, to}}}, "sections_added": [ids],
"sections_removed": [ids]}`.
"""

from typing import Any

Json = dict[str, Any]
SECTIONS = "sections"


def diff_charts(old: Json, new: Json) -> Json:
    diff = _changed_fields(_without_sections(old), _without_sections(new))
    old_sections, new_sections = _by_id(old), _by_id(new)
    changes = {
        section_id: fields
        for section_id, section in new_sections.items()
        if section_id in old_sections
        and (fields := _changed_fields(old_sections[section_id], section))
    }
    added = [section_id for section_id in new_sections if section_id not in old_sections]
    removed = [section_id for section_id in old_sections if section_id not in new_sections]
    for key, value in (
        ("sections", changes),
        ("sections_added", added),
        ("sections_removed", removed),
    ):
        if value:
            diff[key] = value
    return diff


def _without_sections(chart: Json) -> Json:
    return {key: value for key, value in chart.items() if key != SECTIONS}


def _by_id(chart: Json) -> dict[str, Json]:
    return {section["id"]: section for section in chart.get(SECTIONS, [])}


def _changed_fields(old: Json, new: Json) -> Json:
    return {
        key: {"from": old.get(key), "to": new.get(key)}
        for key in old.keys() | new.keys()
        if old.get(key) != new.get(key)
    }
