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

El script levanta un compose **aparte** (proyecto `guitarra-e2e`, con su propio volumen, la API en `127.0.0.1:18000`, Postgres en `127.0.0.1:15432` y los tokens de `.env.e2e`), espera `/api/v1/health`, corre Playwright (Chromium) y lo baja todo con `down -v`, también si algo falla. No toca tu base real, así que se puede correr aunque tengas la app levantada. Deja capturas en `docs/fases/fase-1/capturas/` y `docs/fases/fase-2/capturas/` y el reporte HTML en `e2e/playwright-report/`.

Hay dos recorridos en `e2e/tests/`, en este orden y sobre la misma base vacía:

- `recorrido.spec.ts` (Fase 1): sesión del día, reproducción, Terminé, Progreso, Ajustes, 375 px y Estudio.
- `z-canciones.spec.ts` (Fase 2): pegar un link en Explorar, worker simulado (`POST /jobs/claim` y `/jobs/{id}/result` con el resultado grabado `e2e/fixtures/resultado-grabado.json`, que valida con `AnalysisResult`), canción lista con diagramas y selector clásica/eléctrica, editar un acorde ("Editado por vos"), "Practicar esta sección" + Terminé, Progreso ("Canciones en curso") y 375 px sin scroll horizontal. No usa el worker real ni descarga nada.

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

## Explorar: análisis de canciones

En **Explorar** (`/explorar`) pegás un link de YouTube o Spotify (o buscás por título y artista). La API encola el análisis, el worker lo toma, y cuando la canción pasa a "Lista" abrís su vista: secciones con su línea de tiempo, acordes con diagrama, rasgueo (eléctrica) o arpegio (clásica), BPM, tonalidad y capo.

### Instalar y arrancar el worker

1. Poné en el `.env` de la raíz `GUITAR_API_URL` y `GUITAR_WORKER_TOKEN` (el mismo valor que lee la API; es distinto de `GUITAR_API_TOKEN`).
2. Instalá (idempotente): `.\scripts\install.ps1` crea `worker\.venv`, baja los pesos de beat_this, clona BTC y prepara la caché.
3. Arrancalo: `.\worker\.venv\Scripts\python -m guitarra_worker` (o `--once`), o registralo al iniciar sesión con `.\scripts\worker-tarea.ps1`. Detalles en la sección "Worker de análisis".

### Variables de entorno nuevas

Todas están comentadas en `.env.example`.

| Variable | Para qué |
| --- | --- |
| `GUITAR_WORKER_TOKEN` | Token del worker; solo sirve en `/api/v1/jobs`. Vacío: `/jobs` rechaza todo. |
| `GUITAR_JOB_LEASE_SECONDS` | Segundos de lease de un trabajo antes de volver a la cola (300). |
| `GUITAR_CACHE_DIR` | Caché del worker (por defecto `%USERPROFILE%\GuitarApp\cache`). |
| `GUITAR_BTC_DIR` | Clon de BTC para acordes (por defecto `<caché>\btc`). |
| `GUITAR_BEAT_THIS_CHECKPOINT`, `_SHA256`, `_URL`, `_MIRROR_URL` | Pesos de beat_this (tempo y compases). |
| `GUITAR_FFMPEG` | Ruta a ffmpeg si no está en el `PATH`. |
| `GUITAR_OLLAMA_URL`, `GUITAR_OLLAMA_MODEL`, `GUITAR_OLLAMA_TIMEOUT_S` | Ollama elige el rasgueo del catálogo (`ollama pull qwen2.5:3b`); sin respuesta, usa reglas. |
| `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` | Opcionales, para links de Spotify (developer.spotify.com, flujo client credentials). Sin ellos, YouTube y la búsqueda andan igual. |
| `GUITAR_STRUM_CATALOG` | Catálogo de rasgueos y arpegios que lee la API (por defecto el del repo). |

### Cargar la cifra de Cifra Club a mano

Cifra Club bloquea los pedidos automáticos (403, ver ADR 0012), así que la cifra se carga a mano: abrí la cifra en el navegador, copiá el texto con los acordes, y en la vista de la canción, en el panel "Cifra de Cifra Club", apretá "Cargar cifra", pegalo (y el link como referencia, si querés). Al guardar se reanaliza la canción: el worker alinea esos acordes con el audio y las secciones donde coinciden quedan marcadas "Acordes de Cifra Club". Sin cifra, el análisis termina igual con los acordes detectados.

### Corregir y practicar

- **Corregir:** en la vista de la canción, "Editar sección" permite cambiar el nombre, los tiempos, los acordes (se resuelve la digitación sola) y el patrón de rasgueo o arpegio. Se guarda una versión tuya ("Editado por vos") que gana sobre la automática; "Volver a la automática" la descarta. Reanalizar no pisa tus cambios.
- **Practicar:** "Practicar esta sección" crea un ejercicio de cambio de acordes o de rasgueo con los datos de esa sección. Aparece en "Tus ejercicios" de la canción, con la misma tarjeta de Estudio, y al apretar "Terminé" suma a la racha, al calendario y a "Canciones en curso" de Progreso.

## Arrancar una fase

> Leé `docs/PLAN.md` y `CLAUDE.md`. Arrancá la Fase 1 siguiendo la metodología de `CLAUDE.md`: armá el plan de tareas y mostrámelo antes de delegar.
