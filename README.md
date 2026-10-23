# App de Práctica de Guitarra

Plan: `docs/PLAN.md` · Reglas para agentes: `CLAUDE.md`.

## Preparar el entorno (escritorio Windows)

1. Instalar Git, Python 3.12, Node LTS y Docker Desktop (backend WSL2).
2. Clonar este repo y abrir Claude Code en la carpeta.
3. Instalar las skills que usa el proyecto (en Claude Code):

   ```
   /plugin install superpowers@claude-plugins-official
   /plugin marketplace add anthropics/skills
   /plugin install example-skills@anthropic-agent-skills
   ```

   La primera trae `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion` y las de paralelismo; la segunda trae `frontend-design` y `webapp-testing`.
4. Elegir el modelo del orquestador: `/model opus`.

## Comandos

La CI corre exactamente estos mismos comandos. En PowerShell, desde la raíz del repo:

```powershell
# API (una sola vez: crear el venv e instalar)
py -3.12 -m venv api\.venv
api\.venv\Scripts\python -m pip install -e "api[dev]"

# API: tests y lint (desde api\)
cd api
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
cd ..

# UI
npm ci --prefix ui
npm test --prefix ui
npm run lint --prefix ui
npm run format --prefix ui   # prettier --write
npm run dev --prefix ui      # Vite con proxy a la API
```

Configuración: copiá `.env.example` a `.env` y completá los valores.

```powershell
docker compose up -d --build   # API + Postgres + UI
.\scripts\e2e.ps1              # pruebas E2E con Playwright en un compose aparte
```

## Levantar la app

1. Copiá el archivo de ejemplo y poné tu token:

   ```powershell
   Copy-Item .env.example .env
   ```

   Cambiá `GUITAR_API_TOKEN` (y dejá `VITE_GUITAR_API_TOKEN` igual: la UI lo usa para hablar con la API).
2. Levantá todo (la primera vez compila la UI y tarda unos minutos):

   ```powershell
   docker compose up -d --build
   ```

3. Abrí <http://localhost:8000>. La API migra la base y carga el currículum sola al arrancar.

Qué ver:

- **Hoy** (`/`): la sesión del día, con bloques de ejercicios. Reproducí, probá "Nota por nota" y marcá "Terminé".
- **Estudio** (`/estudio`): niveles, lecciones con su teoría y las tarjetas de ejercicio con mástil y tablatura.
- **Progreso** (`/progreso`): racha actual y máxima, heatmap del último año y avance por nivel.
- **Ajustes** (`/ajustes`): colores del tema, tipografías y zona horaria.

Tus datos viven en el volumen `pgdata` de Docker; reiniciar el compose no los pierde.

## Pruebas E2E

```powershell
.\scripts\e2e.ps1
```

El script levanta un compose **aparte** (proyecto `guitarra-e2e`, con su propio volumen, la API en `127.0.0.1:18000`, Postgres en `127.0.0.1:15432` y el token de `.env.e2e`), espera `/api/v1/health`, corre Playwright (Chromium) y lo baja todo con `down -v`, también si algo falla. No toca tu base real. Deja capturas en `docs/fases/fase-1/capturas/` y el reporte HTML en `e2e/playwright-report/`.

## Worker de análisis

El worker analiza las canciones (descarga, tempo, acordes, estructura). Corre **nativo** en Windows con Python 3.12, nunca en Docker, y habla con la API por `GUITAR_API_URL` + `GUITAR_WORKER_TOKEN` (en el `.env` de la raíz; es distinto del token de la UI).

```powershell
.\scripts\install.ps1                      # venv en worker\.venv, ffmpeg, carpetas de caché y logs (idempotente)
.\worker\.venv\Scripts\python -m guitarra_worker          # a mano; Ctrl+C lo corta
.\worker\.venv\Scripts\python -m guitarra_worker --once   # procesa un solo trabajo y sale
.\scripts\worker-tarea.ps1                 # lo registra para que arranque al iniciar sesión
.\scripts\worker-tarea.ps1 -Remove         # borra la tarea programada
```

La caché vive en `%USERPROFILE%\GuitarApp\cache` (`GUITAR_CACHE_DIR`) y los logs en `%USERPROFILE%\GuitarApp\logs\worker.log`. Tests: `cd worker; .venv\Scripts\pytest`.

## Arrancar una fase

> Leé `docs/PLAN.md` y `CLAUDE.md`. Arrancá la Fase 1 siguiendo la metodología de `CLAUDE.md`: armá el plan de tareas y mostrámelo antes de delegar.
