"""Diccionario de formas de acordes (`guitarra_core`) visto desde la API."""

from typing import Any

from guitarra_core.chord_shapes import shapes_for


def chord_shapes(name: str) -> list[dict[str, Any]]:
    """Formas del acorde, de la más fácil a la más difícil; vacío si no se puede leer."""
    return [
        {
            "name": shape.name,
            "chord": shape.chord,
            "fallback": shape.fallback,
            "difficulty": shape.difficulty,
            **shape.to_notation(),
        }
        for shape in shapes_for(name)
    ]
