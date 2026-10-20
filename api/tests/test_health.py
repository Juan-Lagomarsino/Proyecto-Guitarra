from fastapi.testclient import TestClient

from guitarra_api.main import create_app


def test_health_devuelve_ok():
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
