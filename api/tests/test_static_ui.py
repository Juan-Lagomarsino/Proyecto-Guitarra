from fastapi.testclient import TestClient

from guitarra_api.main import create_app


def _dist(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>UI</html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return tmp_path


def test_sirve_index_en_la_raiz(tmp_path):
    client = TestClient(create_app(ui_dist=_dist(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "UI" in response.text


def test_sirve_assets(tmp_path):
    client = TestClient(create_app(ui_dist=_dist(tmp_path)))

    assert client.get("/assets/app.js").text == "console.log(1)"


def test_ruta_de_la_spa_cae_en_index(tmp_path):
    client = TestClient(create_app(ui_dist=_dist(tmp_path)))

    response = client.get("/estudio/ejercicio/3")

    assert response.status_code == 200
    assert "UI" in response.text


def test_api_inexistente_no_cae_en_index(tmp_path):
    client = TestClient(create_app(ui_dist=_dist(tmp_path)))

    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert "UI" not in response.text


def test_sin_dist_la_api_arranca_igual(tmp_path):
    client = TestClient(create_app(ui_dist=tmp_path / "no-existe"))

    assert client.get("/").status_code == 404
