from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repo: config.py -> guitarra_api -> src -> api -> raíz.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Configuración por variables de entorno (la zona horaria vive en la tabla Settings)."""

    # Si el .env no existe, pydantic-settings lo ignora.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    guitar_api_url: str = "http://localhost:8000"
    guitar_api_token: str = ""
    # Default solo para desarrollo local; en otros entornos se define por variable.
    database_url: str = "postgresql+psycopg://guitarra:guitarra@localhost:5432/guitarra"
