#!/usr/bin/env bash
# E2E en Linux sin Docker (Naxxon, la nube): Postgres existente + API nativa + Playwright.
# Equivale a scripts/e2e.ps1 pero sin compose. Crea la base desde cero cada vez.
#
# Variables (todas opcionales):
#   E2E_PG_HOST/E2E_PG_PORT/E2E_PG_USER  Postgres a usar (default 127.0.0.1 / 5433 / guitarra, trust)
#   E2E_DB          base descartable que se recrea (default e2e_f3)
#   E2E_PYTHON      intérprete con la API instalada (default api/.venv/bin/python, o python3)
#   E2E_PORT        puerto de la API (default 18000)
#   E2E_CHROMIUM_PATH  Chromium ya instalado (default /opt/pw-browsers/chromium si existe)
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pg_host="${E2E_PG_HOST:-127.0.0.1}"
pg_port="${E2E_PG_PORT:-5433}"
pg_user="${E2E_PG_USER:-guitarra}"
db="${E2E_DB:-e2e_f3}"
port="${E2E_PORT:-18000}"
token="e2e-token-de-prueba"
worker_token="e2e-worker-token-de-prueba"
python="${E2E_PYTHON:-$root/api/.venv/bin/python}"
[ -x "$python" ] || python="$(command -v python3)"
if [ -z "${E2E_CHROMIUM_PATH:-}" ] && [ -x /opt/pw-browsers/chromium ]; then
  export E2E_CHROMIUM_PATH=/opt/pw-browsers/chromium
fi

audio_dir="$(mktemp -d)"
api_log="$audio_dir/api.log"
api_pid=""
cleanup() {
  [ -n "$api_pid" ] && kill "$api_pid" 2>/dev/null || true
  rm -rf "$audio_dir"
}
trap cleanup EXIT

psql -h "$pg_host" -p "$pg_port" -U "$pg_user" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS $db WITH (FORCE)" -c "CREATE DATABASE $db"

echo "Compilando la UI ..."
(cd "$root/ui" && { [ -d node_modules ] || npm ci; } &&
  VITE_GUITAR_API_TOKEN="$token" npm run build)

export DATABASE_URL="postgresql+psycopg://$pg_user@$pg_host:$pg_port/$db"
export GUITAR_API_TOKEN="$token" GUITAR_WORKER_TOKEN="$worker_token"
export GUITAR_UI_DIST="$root/ui/dist" GUITAR_CURRICULUM_DIR="$root/curriculum"
export GUITAR_STRUM_CATALOG="$root/worker/src/guitarra_worker/strum/catalog.json"
export GUITAR_AUDIO_DIR="$audio_dir/audio"
export PYTHONPATH="$root/api/src:$root/core/src"

cd "$root/api"
# Con `python -m alembic` la carpeta api/alembic taparía al paquete; se usa el ejecutable del venv.
"$(dirname "$python")/alembic" upgrade head
"$python" -m guitarra_api.infra.curriculum_loader
"$python" -m uvicorn guitarra_api.main:app --port "$port" >"$api_log" 2>&1 &
api_pid=$!

for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:$port/api/v1/health" >/dev/null 2>&1 && break
  kill -0 "$api_pid" 2>/dev/null || { cat "$api_log"; echo "La API murió" >&2; exit 1; }
  sleep 1
done

cd "$root/e2e"
[ -d node_modules ] || npm ci
E2E_BASE_URL="http://127.0.0.1:$port" npx playwright test "$@"
