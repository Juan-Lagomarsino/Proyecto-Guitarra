# 0013 — Audio para el navegador: AAC en .m4a, subido por el worker

- Fecha: 2026-11-02
- Estado: aceptada
- Fase: 3

## Contexto

La UI tiene que reproducir el original (y más adelante la mezcla sin guitarra) con velocidad variable y loop. El audio lo produce el worker, que no toca la base ni el volumen de la API. El navegador reproduce con `<audio src>`, que no puede mandar el header `Authorization`.

## Decisión

- **Formato:** AAC en contenedor `.m4a` (`Content-Type: audio/mp4`), generado con el ffmpeg que ya usa el worker. Lo reproducen Chrome, Firefox, Safari y el celular. El WAV de 48 kHz queda solo en la caché del worker.
- **Subida:** `POST /api/v1/jobs/{job_id}/assets/{kind}` con el token del worker y el cuerpo binario crudo (sin multipart). `kind` es `original`, `no_guitar` o `stem`. La API escribe por streaming a un temporal y lo renombra (reemplazo atómico), con tope `GUITAR_AUDIO_MAX_BYTES` (200 MB por defecto; 413 si se pasa). Un formato distinto de `audio/mp4` da 415 y un cuerpo vacío 422.
- **Almacenamiento:** `GUITAR_AUDIO_DIR/<song_id>/<kind>.<format>`; en Docker, volumen `audio`. `audio_assets` tiene `unique(song_id, kind)`: volver a subir reemplaza.
- **Descarga:** `GET /api/v1/songs/{id}/audio/{kind}` con token de la UI, `Accept-Ranges: bytes`, un solo rango (`206` + `Content-Range`; rango inválido o fuera del archivo, `416`). El detalle de canción lista `audio: [{kind, format, url}]`.
- **Autenticación de `<audio src>`:** solo este endpoint de lectura acepta el token de la UI también como `?token=`. Es el mismo token que ya está en el bundle de la UI; el del worker no sirve ahí. Riesgo: el token puede quedar en logs de acceso; es aceptable en una app personal en localhost/LAN.

## Alternativas consideradas

- WAV/FLAC al navegador: pesan 10 veces más y Safari/celular no los tratan igual de bien en streaming.
- Opus en `.webm`/`.ogg`: Safari antiguo no lo reproduce.
- Subida multipart: obliga a depender de `python-multipart` y a bufferizar; el cuerpo crudo se escribe a disco sin pasar por memoria.
- Compartir un volumen con el worker: el worker corre nativo en Windows, fuera de Docker.
- Descargar con `fetch` + blob URL (sin token en la URL): pierde streaming y range requests.

## Consecuencias

Se puede hacer seek y loop sin bajar el archivo entero. El audio vive en un volumen aparte que hay que incluir en el backup. Hay que vigilar que el token por query no se loguee fuera de la máquina.
