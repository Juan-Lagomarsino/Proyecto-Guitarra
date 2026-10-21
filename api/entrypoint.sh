#!/bin/sh
set -e

# Migra la base y después levanta la API (la UI compilada la sirve la propia API).
alembic upgrade head
# Carga (upsert) el currículum de GUITAR_CURRICULUM_DIR; si el contenido no valida, frena el arranque.
python -m guitarra_api.infra.curriculum_loader
exec uvicorn guitarra_api.main:app --host 0.0.0.0 --port 8000
