from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from guitarra_api.infra.db.session import get_session
from guitarra_api.main import create_app


def _client_con_sesion(session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_health_devuelve_ok_con_db_ok():
    response = _client_con_sesion(MagicMock()).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_devuelve_503_si_la_db_no_conecta():
    session = MagicMock()
    session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("caída"))

    response = _client_con_sesion(session).get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "ok", "db": "error"}
