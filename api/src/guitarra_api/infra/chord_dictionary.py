"""Diccionario de formas de acordes (`guitarra_core`) visto desde la API."""

from typing import Any

from guitarra_core.instrument import shapes_with_capo


def chord_shapes(name: str, capo: int = 0) -> list[dict[str, Any]]:
    """Formas del acorde (según el capo), de la más fácil a la más difícil; vacío si no se lee."""
    return [
        {
            "name": shape.name,
            "chord": shape.chord,
            "fallback": shape.fallback,
            "difficulty": shape.difficulty,
            **shape.to_notation(),
        }
        for shape in shapes_with_capo(name, capo)
    ]
