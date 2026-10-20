#!/bin/sh
set -e

# Migra la base y después levanta la API (la UI compilada la sirve la propia API).
alembic upgrade head
exec uvicorn guitarra_api.main:app --host 0.0.0.0 --port 8000
