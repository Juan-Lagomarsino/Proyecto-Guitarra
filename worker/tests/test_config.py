from pathlib import Path

from guitarra_worker.config import Settings


def test_lee_el_env(tmp_path, monkeypatch):
    for var in ("GUITAR_API_URL", "GUITAR_WORKER_TOKEN", "GUITAR_CACHE_DIR"):
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "GUITAR_API_URL=http://x:1\nGUITAR_WORKER_TOKEN=t0k\nGUITAR_CACHE_DIR="
        f"{tmp_path / 'c' / 'cache'}\nPOSTGRES_USER=ignorado\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=env)
    assert (s.api_url, s.worker_token) == ("http://x:1", "t0k")
    assert s.cache_dir == tmp_path / "c" / "cache"
    assert s.logs_dir == tmp_path / "c" / "logs"


def test_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("GUITAR_CACHE_DIR", raising=False)
    monkeypatch.delenv("GUITAR_WORKER_ID", raising=False)
    s = Settings(_env_file=tmp_path / "no-existe.env")
    assert s.cache_dir == Path.home() / "GuitarApp" / "cache"
    assert s.worker_id
