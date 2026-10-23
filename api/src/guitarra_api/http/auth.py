import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from guitarra_api.config import Settings

_bearer = HTTPBearer(auto_error=False)


def get_api_settings() -> Settings:
    return Settings()


def require_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_api_settings)],
) -> None:
    """Exige `Authorization: Bearer <GUITAR_API_TOKEN>`. Sin token configurado, rechaza todo."""
    expected = settings.guitar_api_token
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
