import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from guitarra_api.config import Settings

_bearer = HTTPBearer(auto_error=False)


def get_api_settings() -> Settings:
    return Settings()


def _check_bearer(credentials: HTTPAuthorizationCredentials | None, expected: str) -> None:
    if (
        not expected
        or credentials is None
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_api_settings)],
) -> None:
    """Exige `Authorization: Bearer <GUITAR_API_TOKEN>`. Sin token configurado, rechaza todo."""
    _check_bearer(credentials, settings.guitar_api_token)


def require_worker_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_api_settings)],
) -> None:
    """Exige `Bearer <GUITAR_WORKER_TOKEN>` (solo /jobs). Sin token configurado, rechaza todo."""
    _check_bearer(credentials, settings.guitar_worker_token)


def require_audio_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_api_settings)],
    token: str | None = None,
) -> None:
    """Token de la UI por header o, solo para leer audio, por `?token=`.

    `<audio src>` no puede mandar `Authorization`; por eso este endpoint (y solo este) acepta
    el mismo token de la UI como query param (ADR 0013).
    """
    if credentials is None and token is not None:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    _check_bearer(credentials, settings.guitar_api_token)
