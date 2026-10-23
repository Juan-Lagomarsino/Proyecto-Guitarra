# Fase 2 — Explorar: análisis de canciones

Estado: **en curso** (plan aprobado por Juan Pedro el 2026-10-23)
Referencia: `docs/PLAN.md` § Explorar, § Pipeline de análisis de canciones, § Modelo de datos (`Song*`, `AudioAsset`, `AnalysisJob`, `Correction`), § Contratos de API, § UI y diseño (diagramas de acordes, vista de canción).

## Criterios de aceptación de la fase (del plan)

1. Pegar un link de YouTube o de Spotify crea la canción y el worker del escritorio la procesa.
2. Resultado: BPM, tonalidad, secciones con tiempos, acordes por sección con diagramas, rasgueo propuesto; clásica y eléctrica.
3. Cruce con Cifra Club cuando existe; si falla, el pipeline termina igual.
4. Probado con 5 canciones del usuario ("Flaca", "De música ligera", "Boys Don't Cry", "Cerca del fuego", "No voy en tren"); los acordes coinciden con Cifra Club en la mayoría de las secciones.
5. Edición de acordes y rasgueo en la UI; la versión del usuario gana.
6. Una canción puede partirse en ejercicios que suman al progreso.

## Decisiones de partida (se registran como ADR en la tarea indicada)

- **Worker:** paquete Python propio en `worker/` (`guitarra_worker`), Python 3.12 nativo con venv, nunca en Docker. Habla con la API solo por `GUITAR_API_URL` + un token propio (`GUITAR_WORKER_TOKEN`), distinto del de la UI. No toca la base. — ADR en T05.
- **Cola:** tabla `analysis_jobs` en Postgres; `POST /jobs/claim` toma con `FOR UPDATE SKIP LOCKED` y un lease con vencimiento; si el worker muere, el trabajo vuelve a la cola al vencer el lease. Reintentos con tope.
- **Pipeline por pasos con caché:** cada paso (fuente, descarga, tempo, acordes, estructura, Cifra Club, rasgueo, armado) es un módulo con interfaz común, guarda su salida en disco (`GUITAR_CACHE_DIR`, por `youtube_id`) y se puede re-ejecutar solo. El pipeline no conoce HTTP; el cliente de la API es un adaptador.
- **Demucs pasa a la Fase 3.** Ningún criterio de la Fase 2 usa pistas separadas, y Demucs en CPU es lo más lento del pipeline. Se suma en la Fase 3, donde se necesita la mezcla "sin guitarra". Si el spike (T01) muestra que los acordes mejoran mucho con pistas armónicas, se vuelve a traer. — ADR en T01.
- **Riffs (paso 7 del pipeline) quedan para la Fase 5**, como dice el plan.
- **Herramientas de análisis:** se eligen en el spike T01 midiendo con las 5 canciones, no por preferencia. Restricción dura: que instalen y corran en Windows 11 con Python 3.12 en CPU.
- **Formato:** el contenido del `SongChart` se define como modelo Pydantic en `domain/` y reusa `chords` y `strum` del formato de notación; confianza por campo (0–1). Un solo validador, JSON Schema exportado y tipos TS generados, igual que la notación.
- **Rasgueo:** catálogo de patrones (rasgueos y arpegios p-i-m-a) + reglas por compás y tempo + densidad de ataques; Ollama elige del catálogo con salida JSON validada. **Si Ollama no responde, se usan solo las reglas**: el pipeline nunca falla por el LLM.
- **Canción → ejercicios:** `Exercise.song_section_id` (exclusivo con `lesson_id`, con check en la base). Un ejercicio de canción se completa con el mismo "Terminé" y suma a la racha igual que los de Estudio.
- **Fuera de la Fase 2:** audio y acompañamiento (Fase 3), separación de pistas (Fase 3), riffs en tablatura (Fase 5), presets (Fase 4b).

### Decisiones de Juan Pedro al aprobar (2026-10-23)

- **Spotify después:** el adaptador se hace completo, pero se activa cuando estén `SPOTIFY_CLIENT_ID` y `SPOTIFY_CLIENT_SECRET` en el `.env`. Mientras tanto, YouTube y nombre + artista.
- **Ollama con modelo chico** (~2 GB, tipo `qwen2.5:3b`), y fallback por reglas siempre.
- **Demucs a la Fase 3** (ADR en T01).

## Tareas

Leyenda: **Ola** = tareas independientes entre sí, en paralelo (worktree propio); cada ola arranca cuando sus dependencias están mergeadas.

| Id | Ola | Objetivo | Depende de | Estado |
| --- | --- | --- | --- | --- |
| F2-T01 | 0 | Spike: elegir herramientas de tempo, acordes, tonalidad y estructura midiendo con las 5 canciones | — | pendiente |
| F2-T02 | 0 | Modelo de datos de canciones, esquema del `SongChart` y migración | — | pendiente |
| F2-T03 | 1 | API de canciones (alta por link o nombre, biblioteca, detalle, chart) | T02 | pendiente |
| F2-T04 | 1 | API de la cola de trabajos para el worker | T02 | pendiente |
| F2-T05 | 1 | Worker: esqueleto, pipeline por pasos con caché, cliente de API, `install.ps1` | T02 | pendiente |
| F2-T06 | 2 | Pasos de fuente y descarga: YouTube, Spotify y búsqueda por duración | T05 | pendiente |
| F2-T07 | 2 | Paso de tempo y compases | T01, T05 | pendiente |
| F2-T08 | 2 | Paso de tonalidad y acordes | T01, T05 | pendiente |
| F2-T09 | 2 | Paso de estructura (secciones con tiempos y nombres) | T01, T05 | pendiente |
| F2-T10 | 2 | Adaptador de Cifra Club y alineación con lo detectado | T05 | pendiente |
| F2-T11 | 2 | Diccionario de acordes y adaptación al instrumento (clásica / eléctrica) | T02 | pendiente |
| F2-T12 | 3 | Rasgueo y arpegio: catálogo, reglas y elección con Ollama | T05, T07 | pendiente |
| F2-T13 | 3 | Armado del `SongChart` y pipeline de punta a punta | T06–T12 | pendiente |
| F2-T14 | 1 | UI: diagrama de acorde vertical con cejilla | T02 | pendiente |
| F2-T15 | 2 | UI: Explorar (pegar link, biblioteca con estado del análisis) | T03 | pendiente |
| F2-T16 | 3 | UI: vista de canción (secciones, acordes, rasgueo, clásica/eléctrica, confianza) | T03, T14 | pendiente |
| F2-T17 | 4 | Correcciones: editar acordes y rasgueo, versión de usuario, historial | T16 | pendiente |
| F2-T18 | 4 | Canción → ejercicios que suman al progreso | T03, T16 | pendiente |
| F2-T19 | 5 | Validación con las 5 canciones, ajuste fino, E2E y README | todas | pendiente |

### F2-T01 — Spike de herramientas de análisis

- **Archivos:** `spikes/analisis/` (scripts y notas, no código de producción), `docs/adr/0006-herramientas-de-analisis.md`, `docs/adr/0007-demucs-en-fase-3.md`.
- **Qué:** bajar el audio de las 5 canciones con yt-dlp (en caché local, nunca al repo) y probar candidatos en Windows + Python 3.12 + CPU. Tempo y compases: beat_this, madmom, librosa. Acordes: BTC, Chordino (vamp / chord-extractor), modelos de madmom, otros que aparezcan. Tonalidad: perfil Krumhansl sobre chroma u otros. Estructura: segmentación por autosimilitud (librosa) u otros.
- **Medir:** BPM contra el de referencia, coincidencia de acordes contra Cifra Club por sección (a mano, cargada como fixture), tiempo de proceso por canción, y si instala sin compilar nada raro.
- **Criterio:** ADR con tabla de mediciones por canción y herramienta, la elección y lo descartado con su motivo. Las referencias de Cifra Club de las 5 canciones quedan como fixtures en `worker/tests/fixtures/` para T19.

### F2-T02 — Modelo de datos y esquema del chart

- **Archivos:** `api/src/guitarra_api/domain/song_chart.py` (Pydantic: secciones, acordes por sección con tiempos, rasgueo, arpegio, tonalidad, capo, confianza por campo), export a `schemas/song_chart.schema.json` y tipos TS generados (`ui/src/songs/types.ts`), modelos `Song`, `SongSection`, `SongChart`, `AudioAsset`, `AnalysisJob`, `Correction`, columna `Exercise.song_section_id` con check de exclusividad, migración `0003`.
- **Criterio:** validación con casos válidos e inválidos; test de que el JSON Schema commiteado está al día; migración ida y vuelta; restricciones: `youtube_id` único, check de `lesson_id` XOR `song_section_id`, versión de chart creciente por canción e instrumento.

### F2-T03 — API de canciones

- **Archivos:** `domain/song_source.py` (parseo puro de URLs de YouTube y Spotify: watch, youtu.be, shorts, music.youtube, open.spotify.com/track, con y sin parámetros), router `songs.py`, servicio de aplicación.
- **Endpoints:** `POST /songs` (`{url}` o `{title, artist}`, crea y encola el análisis, idempotente por `youtube_id` o por id de Spotify), `GET /songs`, `GET /songs/{id}` (con estado del análisis), `GET /songs/{id}/chart?instrument=`, `POST /songs/{id}/reanalyze`.
- **Criterio:** tests del parser con links reales de cada forma y links inválidos; idempotencia; 401/404/422; la última versión de origen `usuario` gana sobre `auto` en `GET chart`.

### F2-T04 — API de la cola de trabajos

- **Archivos:** router `jobs.py`, dependencia de auth con `GUITAR_WORKER_TOKEN`, servicio de cola.
- **Endpoints:** `POST /jobs/claim` (devuelve el trabajo con lo que el worker necesita o 204), `POST /jobs/{id}/result` (guarda metadatos de la canción, secciones y un `SongChart` de origen `auto` por instrumento), `POST /jobs/{id}/fail` (error, reintento con tope), heartbeat para extender el lease.
- **Criterio:** tests: dos claims concurrentes no toman el mismo trabajo; el lease vencido vuelve a la cola; reintentos con tope y después `error`; el token de la UI no sirve en `/jobs` y el del worker no sirve en el resto; `result` valida el chart con el esquema de T02.

### F2-T05 — Worker: esqueleto

- **Archivos:** `worker/pyproject.toml`, `worker/src/guitarra_worker/` (loop de claim con backoff, interfaz `Step`, ejecutor con caché por paso, cliente de API con `httpx`, config por env), `worker/tests/`, `scripts/install.ps1` (idempotente: venv del worker, ffmpeg vía winget si falta, `yt-dlp -U`), `scripts/worker-tarea.ps1` (registra el worker en el Programador de tareas al iniciar sesión), `docs/adr/0008-worker-y-cola.md`. Suma el worker a la CI (pytest + ruff).
- **Criterio:** tests con pasos falsos: el ejecutor re-ejecuta solo los pasos sin caché o fallidos; un paso que falla manda `fail` con el error; el loop respeta el backoff sin trabajos; `install.ps1` corre dos veces seguidas sin errores.

### F2-T06 — Fuente y descarga

- **Archivos:** `worker/.../steps/source.py`, `steps/download.py`, adaptadores `youtube.py` (yt-dlp: metadatos, búsqueda, descarga a WAV 48 kHz con ffmpeg) y `spotify.py` (Web API con client credentials: título, artista, duración, año).
- **Criterio:** función pura de elección del resultado de YouTube (duración ±3 s, desempate por similitud de título, descarta "live", "cover" o "karaoke" salvo que estén en el título buscado) con tests; caché por `youtube_id`; los adaptadores se testean con respuestas grabadas, sin red en la CI. Sin credenciales de Spotify, un link de Spotify falla con un mensaje claro y el resto sigue andando.

### F2-T07 — Tempo y compases

- **Archivos:** `steps/tempo.py` con la herramienta elegida en T01.
- **Criterio:** salida con BPM, grilla de beats y primer tiempo de cada compás; tests con audio sintético (clicks a BPM conocido, ±1 BPM) y con un fragmento corto de prueba generado en el test.

### F2-T08 — Tonalidad y acordes

- **Archivos:** `steps/chords.py`, `steps/key.py`.
- **Criterio:** línea de tiempo de acordes ajustada a la grilla de beats, con confianza por acorde; acordes de duración menor a un beat se fusionan; tests con audio sintético (acordes generados con tonos conocidos) y casos de borde (silencio, una sola nota).

### F2-T09 — Estructura

- **Archivos:** `steps/structure.py`.
- **Criterio:** secciones con inicio, fin y orden, alineadas a compases; nombres heurísticos (intro, estrofa, estribillo, puente, final) según repetición y posición; tests con matrices de autosimilitud sintéticas (A B A B C B) y casos de borde (canción sin repeticiones, canción muy corta).

### F2-T10 — Cifra Club

- **Archivos:** `worker/.../adapters/cifraclub.py` (búsqueda por título y artista, parseo de acordes por sección y capo), `domain/alignment.py` (alineación por distancia de edición entre la secuencia de Cifra Club y la detectada, mezcla de confianza).
- **Criterio:** parser testeado con HTML grabado de 2 o 3 páginas (fixtures); alineación pura con tests (iguales, transpuestas, con inserciones y omisiones); si el sitio falla, no encuentra o cambia el HTML, el paso devuelve "sin datos" y el pipeline sigue. Respetar un intervalo entre pedidos.

### F2-T11 — Diccionario de acordes y adaptación al instrumento

- **Archivos:** `api/src/guitarra_api/domain/chord_shapes.py` (o en un paquete compartido, a decidir en la tarea): de nombre de acorde a formas (abiertas, con cejilla, power chord), con cejilla marcada; reglas de clásica (preferir abiertas, sugerir capo o cejilla) y eléctrica (opción power chords).
- **Criterio:** tests: mayores, menores, séptimas, sus, add9, barras (`C/G`) y acordes raros con fallback; elección de capo que minimiza cejillas para una progresión; toda forma generada valida con el esquema (`shape` de 6, trastes 0–24).

### F2-T12 — Rasgueo y arpegio

- **Archivos:** `worker/.../strum/catalog.json` (patrones con nombre, compás, estilo, versión p-i-m-a para clásica), `strum/rules.py`, `strum/ollama_chooser.py` (prompt acotado, salida JSON validada contra el catálogo, timeout), `docs/adr/0009-modelo-local-para-rasgueo.md`.
- **Criterio:** reglas puras testeadas (compás 3/4 no recibe patrones de 4/4, tempos altos reciben patrones más simples); el chooser con un Ollama falso valida y rechaza salidas fuera del catálogo; sin Ollama, cae a reglas sin error.

### F2-T13 — Armado del chart y pipeline completo

- **Archivos:** `steps/assemble.py`, registro de todos los pasos en el orden del plan.
- **Criterio:** dado lo de los pasos anteriores, arma un `SongChart` por instrumento (clásica y eléctrica) que valida con el esquema; prioriza nombres de Cifra Club con tiempos detectados cuando la alineación es buena; corrida de punta a punta con una canción real en local (no en la CI), con el resultado visible en `GET /songs/{id}/chart`.

### F2-T14 — UI: diagrama de acorde

- **Archivos:** `ui/src/components/ChordDiagram/`.
- **Skill:** `frontend-design`. Estilo coherente con el mástil de la Fase 1.
- **Criterio:** SVG vertical, 6 cuerdas y 4 o 5 trastes, traste inicial indicado cuando no es el 1, cejilla dibujada, cuerdas al aire (o) y muteadas (x), digitación opcional, tónica destacada; solo tokens. Tests de cada caso.

### F2-T15 — UI: Explorar

- **Archivos:** `ui/src/features/explore/`, habilitar Explorar en la navegación.
- **Criterio:** campo para pegar un link o buscar por nombre + artista, con validación y error legible; biblioteca de canciones con estado del análisis (en cola, procesando con paso actual, listo, error con reintentar) que se actualiza sola mientras hay trabajos; tests con la API mockeada; 375 px.

### F2-T16 — UI: vista de canción

- **Archivos:** `ui/src/features/song/`.
- **Skill:** `frontend-design`.
- **Criterio:** cabecera con título, artista, BPM, tonalidad y capo; selector clásica / eléctrica; secciones como línea de tiempo clickeable; por sección, acordes con diagrama y rasgueo (o arpegio en clásica); lo de baja confianza en otro color con leyenda; marca de "acordes de Cifra Club" cuando aplica. Tests con datos de ejemplo; 375 px.

### F2-T17 — Correcciones

- **Archivos:** API `PUT /songs/{id}/chart` (nueva versión, origen `usuario`, `Correction` con el diff), UI de edición en el lugar (cambiar acorde, mover límites de sección, renombrar sección, cambiar el patrón de rasgueo del catálogo).
- **Criterio:** tests: la versión del usuario gana en `GET chart` aunque después llegue un `auto` nuevo (reanálisis); el diff guardado refleja lo cambiado; la UI guarda, muestra "editado por vos" y permite volver a la versión automática.

### F2-T18 — Canción → ejercicios

- **Archivos:** API para crear un ejercicio a partir de una sección (`POST /songs/{id}/sections/{sid}/exercises` con tipo: cambio de acordes, rasgueo; nombre y bpm sugeridos), servicio que arma la notación (acordes + rasgueo de la sección); UI: botón "Practicar esta sección" y la tarjeta de ejercicio de la Fase 1 reutilizada.
- **Criterio:** tests: el ejercicio de canción se completa con "Terminé" y suma a la racha y al calendario; `GET /progress/summary` suma "canciones en curso"; la sesión del día no se rompe con ejercicios de canción (quedan fuera del planificador en esta fase).

### F2-T19 — Validación con las 5 canciones y cierre

- **Archivos:** `worker/tests/validacion/` (script que corre las 5, compara con las fixtures de Cifra Club por sección y escribe un reporte), `docs/fases/fase-2/validacion.md`, E2E (pegar link → esperar análisis con un worker real o con un resultado grabado → ver la canción → editar un acorde → crear un ejercicio → Terminé), README.
- **Criterio:** reporte con BPM detectado contra referencia, % de secciones con acordes coincidentes por canción y tiempo de proceso; "la mayoría de las secciones" coincide en las 5 canciones; si alguna no llega, se documenta por qué y qué se ajustó.

## Orden de ejecución

1. Ola 0 en paralelo: T01 (spike), T02 (modelo).
2. Ola 1 en paralelo: T03, T04, T05, T14.
3. Ola 2 en paralelo: T06, T07, T08, T09, T10, T11, T15.
4. Ola 3 en paralelo: T12, T13 (cuando entren sus pasos), T16.
5. Ola 4 en paralelo: T17, T18.
6. Ola 5: T19 y cierre de fase.

## Resumen de cierre

(Se completa al cerrar la fase.)
