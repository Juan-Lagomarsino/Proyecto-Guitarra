from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from guitarra_api.config import Settings
from guitarra_api.http.auth import get_api_settings, require_token
from guitarra_api.infra.chord_dictionary import chord_shapes
from guitarra_api.infra.strum_catalog import load_strum_catalog

MAX_CAPO = 12

router = APIRouter(dependencies=[Depends(require_token)], tags=["catálogos"])


@router.get("/strum-patterns")
def strum_patterns(
    settings: Annotated[Settings, Depends(get_api_settings)],
) -> list[dict[str, Any]]:
    """Catálogo de rasgueos y arpegios (solo lectura); el mismo JSON que usa el worker."""
    return load_strum_catalog(settings.guitar_strum_catalog)


@router.get("/chords/shapes")
def shapes_of_chord(
    name: Annotated[str, Query(min_length=1, max_length=20)],
    capo: Annotated[int, Query(ge=0, le=MAX_CAPO)] = 0,
) -> list[dict[str, Any]]:
    """Formas de un acorde, de la más fácil a la más difícil, para recalcular al editar.

    Con `capo`, `name` es el acorde que suena y las formas son las que se tocan con esa cejilla.
    """
    shapes = chord_shapes(name, capo)
    if not shapes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"No entiendo '{name}'")
    return shapes
