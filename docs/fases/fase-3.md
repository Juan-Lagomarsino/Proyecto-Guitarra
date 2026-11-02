# Fase 3 — Acompañamiento

Estado: **en curso** (plan aprobado por Juan Pedro el 2026-11-02)
Referencia: `docs/PLAN.md` § Explorar (Acompañamiento), § Pipeline (paso 3, Demucs), § Contratos de API (`GET /songs/{id}/audio/{tipo}`), § Modelo de datos (`AudioAsset`, `AnalysisJob`), § Acompañamiento por el Rig, ADR 0004 (audio en el navegador) y ADR 0007 (Demucs pasa a la Fase 3).

## Criterios de aceptación de la fase (del plan)

1. Selector con las 4 opciones: metrónomo/batería, original, sin guitarra (experimental), backing generado.
2. Velocidad de 50 % a 100 % sin cambio de tono; loop A-B por sección.
3. El mástil y la tab avanzan sincronizados con el audio.

## Decisiones de partida (se registran como ADR en la tarea indicada)

- **Todo el acompañamiento suena en el navegador en esta fase.** El Rig (Fase 4) lo va a reproducir por su flujo de audio; para eso la UI habla con una interfaz `BackingSource` (play, pausa, posición en segundos de la canción, velocidad, loop A-B) y en la Fase 4b se suma una implementación que delega en el Rig sin tocar la vista.
- **El tiempo de la canción es el reloj de la vista.** Con audio (original, sin guitarra) manda `currentTime` del audio; con lo sintetizado (metrónomo, batería, backing) manda el reloj de Web Audio de ADR 0004. La posición en beats sale de la `beat_grid` del chart (port a TS de `seconds_to_beats`), así acordes, rasgueo, mástil y tab se resaltan con el mismo cálculo en los 4 modos.
- **El audio llega a la API desde el worker.** El worker no toca la base ni el volumen de la API: sube cada archivo por HTTP con su token (`POST /jobs/{id}/assets/{tipo}`), la API lo guarda en `GUITAR_AUDIO_DIR` (volumen del compose) y registra el `AudioAsset`. `GET /songs/{id}/audio/{tipo}` sirve con range requests.
- **Formato para el navegador:** AAC en `.m4a` con el ffmpeg que ya usa el worker (lo reproducen Chrome, Firefox, Safari y el celular; el WAV de 48 kHz queda solo en la caché del worker). — ADR en T01.
- **Demucs como trabajo aparte.** La separación es lo más lento (minutos en CPU); va como tipo de trabajo `separation` que se encola cuando termina el análisis. La canción se puede practicar con las otras 3 opciones mientras tanto; "sin guitarra" aparece cuando está lista. — ADR en T04.
- **Backing generado:** batería + bajo + acordes sintetizados en el navegador a partir del chart (acordes por sección, compás, BPM), sin samples ni archivos. Un generador puro (chart → eventos por beat) y un sintetizador aparte, para testear el arreglo sin audio.
- **Sin IA en el camino de audio:** nada de esto usa Ollama.

### Decisiones de Juan Pedro al aprobar (2026-11-02)

- **Velocidad sin cambio de tono con lo nativo del navegador:** `<audio>` con `playbackRate` y `preservesPitch`, sin librerías. Si a 50 % no convence al escucharlo en la PC, se reevalúa (SoundTouchJS o Rubber Band). — ADR en T02.
- **Síntesis con Web Audio pelado** (sigue ADR 0004, sin Tone.js). — ADR en T06.
- **Demucs solo con el modelo de 6 pistas** (desvío del plan, que pide también el de 4). — ADR en T07.

## Lo que la nube no tiene (y cómo se cubre)

| Falta | Impacto | Qué se hace acá | Qué queda para tu PC |
| --- | --- | --- | --- |
| Pesos de Demucs (Hugging Face y `dl.fbaipublicfiles.com` bloqueados por el proxy) y PyTorch CPU (su índice también) | No se puede correr una separación real | Paso de separación con interfaz y un separador falso en los tests; `install.ps1` baja el modelo | Correr una separación real, escuchar la calidad, medir el tiempo en CPU |
| YouTube bloqueado | No hay canciones reales | Audio sintético generado con ffmpeg y numpy en los tests y el E2E | Validar con 2–3 de tus canciones |
| Docker Hub con 429 | No levanta el compose ni testcontainers | Postgres 16 local para la suite de la API (variable opcional en el `conftest`, ver nota) | `docker compose up` y `scripts/e2e.ps1` |
| Parlantes / oídos | No se puede escuchar | Tests de que la velocidad cambia, `preservesPitch` queda activo y el loop salta | Escuchar que el tono no cambia a 50 % y que el loop no "clickea" |

> **Nota de infraestructura:** para correr la suite de la API acá sin Docker Hub, el `conftest` acepta `GUITAR_TEST_DATABASE_URL` (si está, usa esa base; si no, testcontainers como siempre). La CI no cambia.

## Tareas

Leyenda: **Ola** = tareas independientes entre sí, en paralelo (worktree propio).

| Id | Ola | Objetivo | Depende de | Estado |
| --- | --- | --- | --- | --- |
| F3-T01 | 0 | API: subida de audio por el worker, almacenamiento y `GET /songs/{id}/audio/{tipo}` con range | — | hecha |
| F3-T02 | 0 | UI: transporte de acompañamiento (`BackingSource`) sobre `<audio>` con velocidad sin cambio de tono y loop A-B | — | hecha |
| F3-T03 | 0 | UI: generador puro del arreglo (chart → eventos de batería, bajo y acordes por beat) | — | hecha |
| F3-T04 | 1 | API: tipo de trabajo `separation` (se encola tras el análisis, claim con tipo, result sin chart) | T01 | hecha |
| F3-T05 | 1 | Worker: paso que convierte el original a `.m4a` y lo sube | T01 | hecha |
| F3-T06 | 1 | UI: sintetizador Web Audio y fuentes metrónomo / batería / backing generado | T02, T03 | hecha |
| F3-T07 | 2 | Worker: separación con Demucs, mezcla sin guitarra, caché y subida; `install.ps1` | T04, T05 | pendiente |
| F3-T08 | 2 | UI: panel de acompañamiento en la vista de canción (selector, velocidad, loop por sección) | T01, T02, T06 | pendiente |
| F3-T09 | 3 | UI: sincronía de acordes, rasgueo, mástil y tab con el tiempo del acompañamiento | T08 | pendiente |
| F3-T10 | 4 | Cierre: E2E con audio sintético, README, guía de validación en tu PC | todas | pendiente |

### F3-T01 — Audio en la API

- **Archivos:** config `GUITAR_AUDIO_DIR` (default `<repo>/data/audio` fuera de Docker; volumen `audio` en el compose), servicio de almacenamiento (`infra/audio_store.py`: escribe por streaming, nombre por canción y tipo, reemplazo atómico), router: `POST /jobs/{id}/assets/{tipo}` (token del worker, cuerpo binario, tope de tamaño), `GET /songs/{id}/audio/{tipo}` (token de la UI, `Range`, `206`, `Content-Type` por formato), `audio` en el detalle de la canción (`[{kind, format, url}]`). Migración si hace falta (`unique(song_id, kind)`). ADR del formato.
- **Criterio:** tests: subir y servir completo; `Range: bytes=0-99` → 206 con 100 bytes y `Content-Range`; rango inválido → 416; tipo desconocido → 422; canción o asset inexistente → 404; el token de la UI no sube y el del worker no descarga; volver a subir reemplaza; `.env.example` al día.

### F3-T02 — Transporte de acompañamiento

- **Archivos:** `ui/src/backing/` (`BackingSource` interfaz, `mediaSource.ts` sobre un `HTMLMediaElement` inyectable, `loop.ts` puro).
- **Criterio:** tests con un media falso: velocidad acotada a 0,5–1,0 y `preservesPitch` siempre en `true` (con los prefijos de navegador); loop A-B: al pasar B vuelve a A, A ≥ B se rechaza, sacar el loop sigue de largo; `seek` dentro del loop; la posición se lee del audio, nunca se cuenta.

### F3-T03 — Arreglo del backing generado

- **Archivos:** `ui/src/backing/arrangement.ts` (puro).
- **Criterio:** dado un chart (secciones con acordes y tiempos, compás, BPM, `beat_grid`): batería con bombo, redoblante y hi-hat por compás (4/4, 3/4, 6/8), bajo en la fundamental de cada acorde (el bajo de `C/G` es G), acordes en las notas de la forma; eventos en beats, ordenados; tests de borde: acorde que cambia a mitad de compás, sección sin acordes, `N.C.`, compás desconocido cae a 4/4.

### F3-T04 — Trabajo de separación en la API

- **Archivos:** `job_queue.py`, `job_schemas.py`, router `jobs.py`, migración si cambia el check de tipos.
- **Criterio:** al guardar el resultado de un análisis se encola un `separation` si la canción no tiene `sin_guitarra` ni uno activo; el claim devuelve el tipo y lo que necesita (`youtube_id`); `result` de separación no exige chart; reintentos y lease como los de análisis; un reanálisis no re-encola si ya hay pista.

### F3-T05 — Original para el navegador

- **Archivos:** `worker/.../steps/publish_audio.py`, adaptador `ffmpeg` (WAV → m4a AAC), método de subida en `api_client.py`.
- **Criterio:** tests: el comando de ffmpeg se arma bien (sin red, con un ffmpeg falso) y con ffmpeg real sobre un WAV sintético corto; caché: no re-sube si ya subió el mismo archivo; un fallo de subida falla el paso con mensaje claro.

### F3-T06 — Sintetizador y fuentes generadas

- **Archivos:** `ui/src/backing/synth.ts` (Web Audio: osciladores y ruido, sin samples), `generatedSource.ts` (implementa `BackingSource` con el reloj de ADR 0004 y el arreglo de T03), modos `click`, `drums`, `full`.
- **Criterio:** tests con reloj y sink falsos: los eventos se agendan a tiempo con la velocidad aplicada (50 % = el doble de segundos por beat), loop A-B en beats, pausa y cambio de velocidad cancelan lo agendado; nada fijo en colores (no tiene UI).

### F3-T07 — Separación con Demucs

- **Archivos:** `worker/.../steps/separate.py`, adaptador `demucs` (modelo de 6 pistas; "sin guitarra" = suma de todo menos la guitarra), subida del `.m4a`, `install.ps1` (instala `demucs` y baja el modelo con reintentos), README del worker, ADR.
- **Criterio:** tests con un separador falso (pistas sintéticas): la mezcla resta solo la guitarra, sin saturar (normalización), caché por `youtube_id`; si Demucs no está instalado, el trabajo falla con un mensaje que dice cómo instalarlo y el resto de la app sigue andando. **La separación real no se puede correr en la nube (ver tabla).**

### F3-T08 — Panel de acompañamiento

- **Archivos:** `ui/src/features/song/BackingPanel.tsx` y su CSS con tokens.
- **Skill:** `frontend-design`.
- **Criterio:** selector de 4 opciones con "sin guitarra" marcado *experimental* y deshabilitado con motivo mientras no existe ("separando…", "no disponible"); velocidad 50–100 % en pasos de 5 con el BPM resultante; tocar una sección de la línea de tiempo arma el loop A-B de esa sección y se puede sacar; play/pausa; tests con la API y las fuentes mockeadas; 375 px.

### F3-T09 — Sincronía

- **Archivos:** `ui/src/backing/timeline.ts` (segundos ↔ beats con la `beat_grid`, como `seconds_to_beats` de la API), hook `useBackingPosition`, cambios en `SectionTimeline`, `SectionDetail` y `PracticeSection` para tomar la posición del acompañamiento.
- **Criterio:** tests puros de la conversión (iguales a los de Python, mismos casos); con una fuente falsa que avanza, se resaltan la sección, el acorde y el golpe de rasgueo que suenan, y el mástil y la tab de la tarjeta de práctica marcan "suena ahora" en el beat correcto; con loop, el resaltado vuelve con el audio.

### F3-T10 — Cierre

- **Archivos:** E2E (`e2e/tests/`): canción con resultado grabado y audio sintético, elegir cada opción, cambiar velocidad, loop de sección, ver el resaltado avanzar; `docs/fases/fase-3/validacion-en-pc.md` (pasos para escuchar en tu PC: Demucs real, tono a 50 %, loop); README.
- **Criterio:** E2E verde en la nube si Docker Hub responde (si no, se dice y se corre en tu PC); criterios de la fase uno por uno con evidencia, marcando lo que solo se verifica en tu PC.

## Orden de ejecución

1. Ola 0 en paralelo: T01, T02, T03.
2. Ola 1 en paralelo: T04, T05, T06.
3. Ola 2 en paralelo: T07, T08.
4. Ola 3: T09. Ola 4: T10 y cierre.

## Notas de integración

- **F3-T01:** el `url` de `audio` en el detalle es relativo y sin token; la UI le agrega `?token=` para usarlo en `<audio src>` (solo ese endpoint lo acepta). Pendientes menores: si falla el registro después de escribir, queda un archivo huérfano; dos primeras subidas simultáneas del mismo tipo pueden dar 500 por el unique (el worker sube de a una).
- **F3-T04:** contrato para el worker: el claim trae `job_type` (`analyze` | `separation`; gana el análisis si hay de los dos); el `result` de una separación es `{"worker_id": ...}` después de subir `no_guitar` por assets. El detalle de canción trae `separation_status` (`none|queued|running|done|error`). Pendientes menores: el chequeo "¿ya hay separación activa?" + insert no es atómico (en la práctica no hay dos análisis simultáneos de la misma canción); las constantes de tipos de trabajo viven en el repositorio de infra y convendría moverlas a dominio.
