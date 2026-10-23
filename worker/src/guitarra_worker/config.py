"""Configuración del worker por variables de entorno (y el .env de la raíz del repo)."""

import socket
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"


def default_cache_dir() -> Path:
    return Path.home() / "GuitarApp" / "cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GUITAR_", env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    api_url: str = "http://localhost:8000"
    worker_token: str = ""
    cache_dir: Path = Field(default_factory=default_cache_dir)
    worker_id: str = Field(default_factory=socket.gethostname)
    poll_interval_s: float = 2.0
    max_backoff_s: float = 60.0
    heartbeat_interval_s: float = 30.0
    ffmpeg: str | None = None  # GUITAR_FFMPEG: ruta al ejecutable; vacío = el del PATH
    # Spotify es opcional; sin credenciales los links de Spotify fallan con un mensaje claro.
    spotify_client_id: str = Field(default="", validation_alias="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str = Field(default="", validation_alias="SPOTIFY_CLIENT_SECRET")
    cifraclub_base_url: str = "https://www.cifraclub.com"
    cifraclub_min_interval_s: float = 3.0

    @property
    def logs_dir(self) -> Path:
        return self.cache_dir.parent / "logs"
