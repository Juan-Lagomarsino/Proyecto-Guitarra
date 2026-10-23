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
    btc_dir: Path | None = None  # GUITAR_BTC_DIR: clon de BTC; vacío = <cache_dir>/btc

    # beat_this (tempo y compases): ruta del checkpoint y de dónde bajarlo (oficial y espejo)
    beat_this_checkpoint: Path | None = None  # GUITAR_BEAT_THIS_CHECKPOINT
    beat_this_url: str = "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt"
    # SHA-256 del final0.ckpt oficial (GUITAR_BEAT_THIS_SHA256)
    beat_this_sha256: str = "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331"
    beat_this_mirror_url: str = (
        "https://huggingface.co/safe-models/beat-this-final0/resolve/main/model.safetensors"
    )

    # Ollama (elección de rasgueo del catálogo); GUITAR_OLLAMA_URL vacío = solo reglas
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_s: float = 30.0

    @property
    def models_dir(self) -> Path:
        return self.cache_dir.parent / "models"

    @property
    def beat_this_checkpoint_path(self) -> Path:
        return self.beat_this_checkpoint or self.models_dir / "beat_this-final0.ckpt"

    @property
    def btc_path(self) -> Path:
        return self.btc_dir or self.cache_dir / "btc"

    @property
    def logs_dir(self) -> Path:
        return self.cache_dir.parent / "logs"
