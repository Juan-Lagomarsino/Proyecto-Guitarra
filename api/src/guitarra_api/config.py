from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del repo: config.py -> guitarra_api -> src -> api -> raíz.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Configuración por variables de entorno (la zona horaria vive en la tabla Settings)."""

    # Si el .env no existe, pydantic-settings lo ignora.
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    guitar_api_url: str = "http://localhost:8000"
    guitar_api_token: str = ""
    # Token propio del worker de análisis; solo sirve en /jobs. Vacío: /jobs rechaza todo.
    guitar_worker_token: str = ""
    # Segundos que dura el lease de un trabajo antes de volver a la cola si el worker no avisa.
    guitar_job_lease_seconds: int = Field(default=300, gt=0)
    # Default solo para desarrollo local; en otros entornos se define por variable.
    database_url: str = "postgresql+psycopg://guitarra:guitarra@localhost:5432/guitarra"
    # Carpeta con la UI compilada (ui/dist); en Docker la define el Dockerfile.
    guitar_ui_dist: Path = ENV_FILE.parent / "ui" / "dist"
    # Carpeta con los `*.json` del currículum; en Docker la define el Dockerfile.
    guitar_curriculum_dir: Path = ENV_FILE.parent / "curriculum"
    # Catálogo de rasgueos y arpegios (el mismo JSON que usa el worker); en Docker lo fija el
    # Dockerfile.
    guitar_strum_catalog: Path = (
        ENV_FILE.parent / "worker" / "src" / "guitarra_worker" / "strum" / "catalog.json"
    )
