"""python -m guitarra_worker [--once]"""

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler

from guitarra_worker.api_client import ApiClient
from guitarra_worker.config import Settings
from guitarra_worker.loop import run_loop
from guitarra_worker.pipeline.registry import assemble_result, default_steps


def configure_logging(settings: Settings) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            settings.logs_dir / "worker.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:  # pythonw no tiene consola
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guitarra_worker")
    parser.add_argument("--once", action="store_true", help="procesa un solo trabajo y sale")
    args = parser.parse_args(argv)

    settings = Settings()
    configure_logging(settings)
    log = logging.getLogger("guitarra_worker")
    if not settings.worker_token:
        log.error("Falta GUITAR_WORKER_TOKEN (en el entorno o en el .env de la raíz)")
        return 2
    client = ApiClient(settings.api_url, settings.worker_token, settings.worker_id)
    log.info("Worker %s contra %s", settings.worker_id, settings.api_url)
    try:
        run_loop(client, settings, default_steps(), assemble_result, once=args.once)
    except KeyboardInterrupt:
        log.info("Cortado con Ctrl+C")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
