# 0009 — Worker de análisis y cola de trabajos

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

Analizar una canción (descarga, tempo, acordes, estructura) tarda minutos, usa CPU y herramientas nativas (ffmpeg, yt-dlp), y no puede bloquear la API. El plan pide que el worker corra nativo en Windows, hable con la API solo por `GUITAR_API_URL` + token, arranque al iniciar sesión y use CPU por defecto. Un worker puede morir a mitad de un trabajo, y los pasos son caros: no conviene repetirlos.

## Decisión

- **Worker nativo:** paquete `guitarra_worker` en `worker/`, Python 3.12 con venv propio (`worker/.venv`), nunca en Docker. No toca la base: usa `/api/v1/jobs/*` con un token propio (`GUITAR_WORKER_TOKEN`), distinto del de la UI. Todo el HTTP vive en `api_client.py`.
- **Cola en Postgres con lease:** tabla `analysis_jobs`; el worker toma trabajo con `POST /jobs/claim` (en la API, `FOR UPDATE SKIP LOCKED`) y recibe un lease con vencimiento. Si muere, el lease vence y el trabajo vuelve a la cola, con tope de reintentos. Sin trabajo, el worker hace polling con backoff exponencial hasta un máximo (`GUITAR_POLL_INTERVAL_S`, `GUITAR_MAX_BACKOFF_S`).
- **Heartbeat:** al empezar cada paso y cada `heartbeat_interval_s` desde un hilo, con `current_step`. Un 409 significa que el trabajo ya no es del worker: se aborta sin mandar `result` ni `fail`. Si la API no responde (red), el hilo loguea y sigue; el heartbeat de inicio de paso termina en `fail` con `retryable=true`.
- **Caché por paso, encadenada:** cada paso guarda su salida JSON en `<cache>/<youtube_id | song-<id>>/steps/<paso>.json` junto con una clave: un hash corto que combina su nombre y versión con la clave del paso anterior. Se reusa si la clave coincide; si cambia la versión de un paso, se re-ejecuta él y todos los siguientes. Si el archivo está roto, también se re-ejecuta. Escritura atómica (temporal + `os.replace`). Un paso fallido no deja caché, así que el reintento retoma desde ahí.
- **Errores:** `RetryableStepError` (red, timeouts) se informa con `retryable=true`; cualquier otra excepción, con `retryable=false`. Que un paso no encuentre datos (por ejemplo Cifra Club) no es error: devuelve una salida "sin datos".
- **Resultado:** `run_pipeline` recibe una función explícita `assemble(outputs) -> dict` (la define `registry.py`) que arma el cuerpo de `result` (`metadata`, `sections`, `charts`) a partir de las salidas de los pasos por nombre. No se asume que el resultado sea el del último paso.
- **Arranque:** `scripts/worker-tarea.ps1` registra una tarea programada al iniciar sesión (usuario actual, sin elevar) con `pythonw.exe`; `scripts/install.ps1` prepara venv, ffmpeg, carpetas y avisa si falta el token. Logs rotativos en `<cache>/../logs/worker.log`.

## Alternativas consideradas

- Worker en Docker: no ve ASIO ni la GPU, y complica el acceso a ffmpeg y a la caché local.
- Cola en Redis/Celery: otra pieza que mantener para un usuario único; Postgres ya está y alcanza con `SKIP LOCKED`.
- Worker con acceso directo a la base: acopla el pipeline al esquema y obliga a abrir Postgres; la API ya valida el contenido.
- Caché de un solo archivo por canción: obliga a repetir pasos caros ante cualquier cambio de versión de uno solo.

## Consecuencias

- Reanudar un análisis interrumpido es barato; cambiar la `version` de un paso invalida solo ese paso (hay que subirla a mano al cambiar su lógica; los pasos que dependen de él deberían subir la suya también).
- El worker solo corre mientras Juan Pedro tiene la sesión iniciada.
- El contrato de `/jobs/*` es compartido con la API: si cambia, se ajusta solo `api_client.py`.
