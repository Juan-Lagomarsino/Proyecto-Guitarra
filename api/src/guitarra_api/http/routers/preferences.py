from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from guitarra_api.http.auth import require_token
from guitarra_api.infra.db.repositories.chord_preferences import ChordShapePreferenceRepository
from guitarra_api.infra.db.session import get_session

router = APIRouter(
    prefix="/preferences", tags=["preferencias"], dependencies=[Depends(require_token)]
)


@router.get("/chord-shapes")
def chord_shapes(session: Annotated[Session, Depends(get_session)]) -> dict[str, Any]:
    """`{instrumento: {acorde: {forma: peso}}}`; la forma son 6 trastes absolutos (ver core)."""
    return ChordShapePreferenceRepository(session).load().to_json()
