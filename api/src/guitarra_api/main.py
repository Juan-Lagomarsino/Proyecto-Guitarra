from pathlib import Path

from fastapi import FastAPI

from guitarra_api.config import Settings
from guitarra_api.http import health
from guitarra_api.http.routers import study
from guitarra_api.http.static_ui import mount_ui


def create_app(ui_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="App de Práctica de Guitarra")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(study.router, prefix="/api/v1")
    mount_ui(app, ui_dist if ui_dist is not None else Settings().guitar_ui_dist)
    return app


app = create_app()
