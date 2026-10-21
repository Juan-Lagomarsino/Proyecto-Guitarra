# Fase 1 — Base, Estudio y progreso

Estado: **en curso** (plan aprobado por Juan Pedro el 2026-10-20)
Referencia: `docs/PLAN.md` § Fase 1, § Modelo de datos, § Formato interno de notación, § Contratos de API, § UI y diseño.
Referencia visual: `docs/referencias/taller-electrica.html` (HTML original del artefacto). De ahí salen el mástil (`drawBoard`), la tablatura (`drawTab`), la tarjeta de práctica y los colores de `:root` como tema por defecto. **Su notación de tabs (`"6-0+5-2:2"`) es solo referencia visual: el formato oficial es el JSON del plan.**

## Criterios de aceptación de la fase (del plan)

1. `docker compose up` levanta API + Postgres + UI; migraciones automáticas. Repo en GitHub con CI que corre los tests.
2. Currículum con al menos los 3 primeros niveles completos (lecciones, teoría, ejercicios con notación).
3. Mástil y tablatura con el estilo del artefacto; reproducción automática y nota por nota; metrónomo en el navegador.
4. "Terminé" registra la práctica; racha, heatmap y avance por nivel correctos (tests de racha: medianoche, días excluidos).
5. Sesión del día generada según nivel y pendientes.
6. Tema editable por tokens con vista previa, persistido en el server.

## Decisiones de partida (se registran como ADR en la tarea indicada)

- **Estructura del repo:** `api/` (FastAPI, paquete `guitarra_api` con `domain/`, `infra/`, `http/`), `ui/` (Vite + React + TS), `curriculum/` (contenido en JSON), `schemas/` (JSON Schema exportado). — ADR en T01.
- **UI servida por la API:** un solo contenedor `api` con build multi-etapa (Node construye `ui/dist`, FastAPI lo sirve como estáticos). En desarrollo, Vite con proxy a la API. — ADR en T02.
- **Notación:** la fuente de verdad es el modelo Pydantic en `guitarra_api/domain/notation.py`; de ahí se exporta `schemas/notation.schema.json` y se generan los tipos TS. Un test falla si el JSON Schema commiteado quedó viejo. — ADR en T03.
- **Zona horaria:** los días de práctica se calculan en la zona guardada en `Settings.timezone` (IANA, por defecto `America/Montevideo`), editable desde `PUT /settings`. En la base, los timestamps se guardan en UTC.
- **Días excluidos en Fase 1:** la racha los necesita, así que en esta fase se crea `ReminderRules` con `GET/PUT /reminders/rules`. `GET /reminders/status` queda para la Fase 6.
- **Semántica de racha:** un día excluido sin práctica no corta ni suma; si se practica, suma. La racha actual sigue viva si hoy todavía no se practicó pero ayer sí (o el último día no excluido).
- **Nivel actual:** el primer nivel (por orden) que tiene ejercicios nunca completados. **Pendiente:** ejercicio nunca completado o con mejor BPM < objetivo.
- **Token:** todo `/api/v1` excepto `/health` exige `Authorization: Bearer <GUITAR_API_TOKEN>`. La UI lo toma de su config de build (localhost, un solo usuario).
- **Fuera de la Fase 1:** `Song*`, `AudioAsset`, `AnalysisJob`, presets, grabaciones. `Exercise.song_section_id` se agrega en la Fase 2 con su migración.

## Tareas

Leyenda: **Ola** = las tareas de una misma ola son independientes entre sí y van en paralelo (worktree propio); cada ola arranca cuando sus dependencias están mergeadas.

| Id | Ola | Objetivo | Depende de | Estado |
| --- | --- | --- | --- | --- |
| F1-T01 | 0 | Esqueleto del repo, tooling y CI | — | hecha |
| F1-T02 | 1 | Docker Compose con Postgres, API y migraciones automáticas | T01 | integrada (falta verificar con Docker) |
| F1-T03 | 1 | Esquema de notación y su validador | T01 | hecha |
| F1-T04 | 1 | Modelos SQLAlchemy y migración inicial | T01 | integrada (tests de DB pendientes de Docker) |
| F1-T05 | 1 | Dominio: días de práctica y racha | T01 | hecha |
| F1-T06 | 1 | Dominio: generador de la sesión del día | T01 | hecha |
| F1-T07 | 1 | UI: shell, rutas, tokens de tema y cliente de API | T01 | hecha |
| F1-T08 | 2 | Currículum nivel 1 + cargador idempotente | T03, T04 | integrada (test de DB del cargador pendiente de Docker) |
| F1-T09 | 3 | Currículum niveles 2 y 3 | T08 | pendiente |
| F1-T10 | 2 | API de Estudio y "Terminé" | T03, T04 | pendiente |
| F1-T11 | 3 | API de progreso, sesión del día y reglas | T05, T06, T10 | pendiente |
| F1-T12 | 2 | API de ajustes (tema) | T04 | pendiente |
| F1-T13 | 2 | UI: componente Mástil | T03, T07 | hecha |
| F1-T14 | 2 | UI: componente Tablatura | T03, T07 | hecha |
| F1-T15 | 2 | UI: motor de reproducción y metrónomo | T03, T07 | hecha |
| F1-T16 | 4 | UI: tarjeta de ejercicio y vistas de Estudio | T10, T13, T14, T15 | pendiente |
| F1-T17 | 4 | UI: vista de Progreso | T07, T11 | pendiente |
| F1-T18 | 5 | UI: vista de Sesión del día | T11, T16 | pendiente |
| F1-T19 | 4 | UI: ajustes de tema con vista previa | T12, T13 | pendiente |
| F1-T20 | 6 | Pruebas E2E con Playwright y README | todas | pendiente |

### F1-T01 — Esqueleto del repo, tooling y CI

- **Archivos:** `api/pyproject.toml`, `api/src/guitarra_api/` (app FastAPI con `GET /api/v1/health`), `api/tests/`, `ui/` (Vite + React + TS, vitest + Testing Library, eslint + prettier), `.github/workflows/ci.yml`, `.gitignore`, `.env.example`, `README.md` (sección comandos), `docs/adr/0001-estructura-del-repo.md`.
- **Config:** `pydantic-settings` leyendo `GUITAR_API_URL`, `GUITAR_API_TOKEN`, `DATABASE_URL`. (La zona horaria no va por env: vive en `Settings`.)
- **Criterio:** `pytest` (desde `api/`), `ruff check`, `ruff format --check`, `npm test --prefix ui`, `npm run lint --prefix ui` pasan en local; la CI corre exactamente esos comandos y queda verde en GitHub tras el push.

### F1-T02 — Docker Compose

- **Archivos:** `docker-compose.yml`, `api/Dockerfile` (multi-etapa: build de `ui/` + API), `api/entrypoint.sh` (`alembic upgrade head` y luego uvicorn), config de Alembic vacía, `docs/adr/0002-ui-servida-por-la-api.md`.
- **Criterio:** `docker compose up -d` desde cero → `GET http://127.0.0.1:<puerto>/api/v1/health` responde 200 con `db: ok`; `GET /` devuelve el `index.html` de la UI; puertos publicados solo en `127.0.0.1`; volumen nombrado para Postgres; reiniciar el compose no pierde datos.

### F1-T03 — Esquema de notación

- **Archivos:** `api/src/guitarra_api/domain/notation.py`, script de export a `schemas/notation.schema.json`, `ui/src/notation/types.ts` generado (json-schema-to-typescript, script npm), `docs/adr/0003-esquema-de-notacion.md`.
- **Criterio:** tests de validación con casos válidos e inválidos: cuerda fuera de 1–6, traste fuera de 0–24, técnica desconocida, `bend` sin técnica `b`, `shape` de largo ≠ 6, `t`/`dur` negativos, `tonic` inválida, afinación de largo ≠ 6. Test que falla si el JSON Schema commiteado no coincide con el modelo. El ejemplo del plan valida tal cual.

### F1-T04 — Modelos y migración inicial

- **Archivos:** `api/src/guitarra_api/infra/db/` (modelos, sesión), `api/alembic/versions/0001_*.py`.
- **Entidades:** `Level`, `Lesson`, `Exercise` (con `slug` único estable, `type`, `instrument`, `notation` JSONB, `bpm_start`, `bpm_target`, `duration_min`, `category` para la tarjeta), `ExerciseCompletion` (timestamp UTC), `PracticeSession` (fecha local, ejercicios planificados, estado), `Settings` (incluye `timezone`, default `America/Montevideo`) y `ReminderRules` (fila única cada una).
- **Criterio:** `alembic upgrade head` y `downgrade base` funcionan contra un Postgres de test (testcontainers o el del compose); tests de repositorio para alta y consulta básica; restricciones (FK, únicos, checks de bpm > 0).

### F1-T05 — Dominio: días de práctica y racha

- **Archivos:** `api/src/guitarra_api/domain/progress.py` + tests. Funciones puras, sin DB ni FastAPI.
- **Criterio:** dadas completions (UTC), zona horaria, días de semana excluidos y "hoy" → días practicados, racha actual, racha máxima, total de días. Casos de borde con test: completion a las 23:59 y 00:01 locales (y a las 02:30 UTC, que sigue siendo "ayer" en Montevideo), la misma completion con dos zonas distintas cae en días distintos, día excluido sin práctica en medio de la racha, práctica en día excluido, hoy sin practicar con ayer practicado, hoy excluido, sin completions, varias completions el mismo día, racha máxima en el pasado mayor que la actual.

### F1-T06 — Dominio: generador de la sesión del día

- **Archivos:** `api/src/guitarra_api/domain/session_planner.py` + tests. Función pura.
- **Criterio:** dado el currículum (niveles/ejercicios con tipo, categoría y duración), el historial de completions y una semilla → sesión de ~20 min (±5) con bloques en orden calentamiento → técnica → riff → improvisación. Toma pendientes del nivel actual primero; calentamiento puede venir de niveles anteriores ya completados. Determinista para la misma semilla; otra semilla (regenerar) da otra combinación si hay alternativas. Casos de borde: todo completado, nivel sin ejercicios de un bloque (se completa con otro tipo sin pasarse del tiempo), currículum vacío.

### F1-T07 — UI: shell, rutas y tema

- **Archivos:** `ui/src/app/` (layout, navegación Estudio / Progreso / Ajustes; Explorar y Rig como entradas deshabilitadas), React Router, `ui/src/theme/tokens.css` con el tema por defecto tomado de `:root` de la referencia (nombres semánticos del plan: `--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--note-tonic`, `--note-other`, `--note-active`, `--string`, `--fret`…, con los valores de la referencia; la correspondencia con `--ground`, `--panel`, `--sodium`, etc. queda comentada en el archivo), fuentes Anton e IBM Plex Mono, `ui/src/api/client.ts` (URL y token por config), `ThemeProvider` que aplica tokens desde un objeto.
- **Skill:** `frontend-design`.
- **Criterio:** tests de render del shell y de que `ThemeProvider` escribe las variables CSS; eslint sin colores literales fuera de `tokens.css` (regla o test que lo verifique); responsive sin scroll horizontal a 375 px.

### F1-T08 — Currículum nivel 1 + cargador

- **Archivos:** `curriculum/nivel-01-power-chords.json` (formato documentado en `curriculum/README.md`), `api/src/guitarra_api/infra/curriculum_loader.py`, llamado al arrancar después de las migraciones.
- **Contenido:** nivel "Power chords y palm mute": 3–4 lecciones con teoría corta en markdown atada a lo que se toca, 8–12 ejercicios con notación válida, tempo de arranque y objetivo, mezcla de categorías para que la sesión del día tenga material.
- **Criterio:** cada ejercicio valida contra el esquema de T03; el cargador es idempotente por `slug` (correrlo dos veces no duplica y actualiza contenido sin borrar completions); test que lo verifica.

### F1-T09 — Currículum niveles 2 y 3

- **Archivos:** `curriculum/nivel-02-pentatonica-menor.json` (cajas 1 y 2), `curriculum/nivel-03-ligados.json` (hammer-on, pull-off, slide).
- **Criterio:** mismo formato y validación que T08; test que verifica para cada nivel ≥ 3 lecciones, ejercicios de al menos 3 categorías distintas, tónica marcada en escalas, y que las notas de la pentatónica caen en las posiciones correctas (test que calcula la nota de cada evento y la compara con la escala).

### F1-T10 — API de Estudio y "Terminé"

- **Archivos:** `api/src/guitarra_api/http/routers/study.py`, servicios de aplicación, dependencia de auth por token.
- **Endpoints:** `GET /levels`, `GET /levels/{id}/lessons`, `GET /lessons/{id}`, `GET /exercises/{id}` (con mejor BPM), `POST /exercises/{id}/complete` (`bpm_logrado`, `instrumento`).
- **Criterio:** tests de API (httpx + DB de test): 401 sin token, 404 en ids inexistentes, 422 con body inválido, completion persistida con timestamp UTC, mejor BPM correcto. Esquemas visibles en `/docs`.

### F1-T11 — API de progreso, sesión del día y reglas

- **Archivos:** routers `progress.py`, `sessions.py`, `reminders.py` (solo reglas); adaptadores que alimentan T05 y T06 desde la DB, usando la zona de `Settings`.
- **Endpoints:** `GET /progress/summary` (racha actual y máxima, días practicados, avance por nivel), `GET /progress/calendar?from&to`, `GET /sessions/today` (la crea si no existe, persistida en `PracticeSession`), `POST /sessions/today/regenerate`, `GET/PUT /reminders/rules`.
- **Criterio:** tests de API de punta a punta: completar ejercicios cambia racha y calendario; `sessions/today` es estable en el mismo día y cambia con regenerate; marcar un día excluido en las reglas afecta la racha; cambiar la zona en `Settings` cambia el día en que cae una completion cercana a la medianoche.

### F1-T12 — API de ajustes

- **Archivos:** router `settings.py`.
- **Endpoints:** `GET/PUT /settings` (tokens de color, tipografías, instrumento por defecto, afinación, zona horaria). Defaults = tema del artefacto y `America/Montevideo`.
- **Criterio:** tests: GET sin fila devuelve defaults; PUT valida que cada token sea un color CSS válido y que no falte ninguno de la lista conocida; zona horaria IANA válida (rechaza `Mars/Base`); persistencia.

### F1-T13 — UI: Mástil

- **Archivos:** `ui/src/components/Fretboard/`.
- **Skill:** `frontend-design`. Replicar `drawBoard` de la referencia (geometría, proporciones, estilos) como componente React que recibe eventos en el formato JSON oficial.
- **Criterio:** SVG horizontal, cuerdas e B G D A E de arriba a abajo con nombre a la izquierda, números de traste abajo, incrustaciones 3/5/7/9 y doble en 12, notas como círculos con estados tónica / otra / suena ahora y leyenda, rango de trastes por props. Solo tokens CSS. Tests: posición de notas, estados, rango.

### F1-T14 — UI: Tablatura

- **Archivos:** `ui/src/components/Tab/`.
- **Skill:** `frontend-design`. Replicar `drawTab` de la referencia como componente React; la entrada es el JSON oficial, no la notación `"6-0+5-2:2"` de la referencia.
- **Criterio:** seis líneas con nombre de cuerda, números unidos por guiones, partición en sistemas según ancho, anotaciones h p / \ b r ~ pm x, resaltado del evento activo. Tests: partición en sistemas, render de cada técnica, evento activo.

### F1-T15 — UI: reproducción y metrónomo

- **Archivos:** `ui/src/playback/` (hook `usePlayback`: modo automático al BPM elegido y modo nota por nota con "siguiente"/"anterior"; expone índice de evento activo), `ui/src/playback/metronome.ts`, ADR `0004` si se elige Tone.js frente a Web Audio pelado.
- **Criterio:** tests con reloj falso: el evento activo avanza según `t`/`dur` y BPM, cambiar BPM en vivo, pausa/reanudar, nota por nota no avanza solo, fin de ejercicio. Metrónomo con acento en el 1 y tick sincronizado con el transporte.

### F1-T16 — UI: tarjeta de ejercicio y Estudio

- **Archivos:** `ui/src/features/study/` (lista de niveles con avance → lección con teoría en markdown → tarjetas de ejercicio), `ExerciseCard`.
- **Skill:** `frontend-design`.
- **Criterio:** tarjeta según el plan y la tarjeta de práctica de la referencia (categoría en versalitas, título condensado, chips de objetivo / mejor marca / "en la sesión de hoy", descripción con borde de acento, mástil + tab sincronizados con la reproducción, controles de bpm, play, nota por nota y **Terminé** que envía el bpm logrado y actualiza la mejor marca). Tests con API mockeada.

### F1-T17 — UI: Progreso

- **Archivos:** `ui/src/features/progress/`.
- **Criterio:** heatmap de días (último año, intensidad por cantidad de ejercicios), racha actual y máxima, avance por nivel. Tests con datos de ejemplo, incluido el estado vacío.

### F1-T18 — UI: Sesión del día

- **Archivos:** `ui/src/features/session/`; es la pantalla de inicio.
- **Criterio:** muestra los bloques con su duración y las tarjetas reutilizadas de T16, marca lo ya hecho hoy, botón "Regenerar". Tests con API mockeada.

### F1-T19 — UI: Ajustes de tema

- **Archivos:** `ui/src/features/settings/`.
- **Criterio:** selector de color por token, de tipografías y de zona horaria, vista previa en vivo con un mástil de ejemplo, guardar persiste vía `PUT /settings` y se aplica al recargar; botón "volver al tema por defecto". Tests.

### F1-T20 — E2E y README

- **Archivos:** `e2e/` (Playwright), `README.md`.
- **Skill:** `webapp-testing`.
- **Criterio:** contra el compose levantado: abrir la sesión del día, reproducir un ejercicio, nota por nota, marcar Terminé, ver la racha en 1 y el día en el heatmap, cambiar un color del tema, recargar y verlo persistido. Capturas guardadas como evidencia del cierre. README con cómo levantar todo y correr los tests.

## Orden de ejecución

1. Ola 0: T01 (sola; deja la base para todo lo demás).
2. Ola 1 en paralelo: T02, T03, T04, T05, T06, T07.
3. Ola 2 en paralelo: T08, T10, T12, T13, T14, T15.
4. Ola 3 en paralelo: T09, T11.
5. Ola 4 en paralelo: T16, T17, T19.
6. Ola 5: T18.
7. Ola 6: T20 y cierre de fase.

## Resumen de cierre

(Se completa al cerrar la fase.)
