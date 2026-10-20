from fastapi import FastAPI

from guitarra_api.http import health


def create_app() -> FastAPI:
    app = FastAPI(title="App de Práctica de Guitarra")
    app.include_router(health.router, prefix="/api/v1")
    return app


app = create_app()
