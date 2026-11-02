# Worker de análisis

Corre nativo en Windows con Python 3.12 (venv en `worker/.venv`), nunca en Docker.

## Instalar y actualizar

`.\scripts\install.ps1` es idempotente: crea el venv, instala el worker, ffmpeg (winget) y llama a
`Update-YtDlp`, que hace `pip install -U yt-dlp` en el venv. YouTube cambia seguido; si una
descarga empieza a fallar, volvé a correr `.\scripts\install.ps1` antes de buscar otra causa.

## Acordes y tonalidad (BTC)

Los pasos `chords` y `key` usan BTC (vocabulario `voca`, ADR 0006). `install.ps1` instala torch
(rueda CPU) y demás con `pip install -e worker[analysis]`, y clona `jayg996/BTC-ISMIR19` en
`<GUITAR_CACHE_DIR>/btc` (o `GUITAR_BTC_DIR`) en un commit fijo; correrlo de nuevo es seguro. Los
dos arreglos de compatibilidad (`yaml.safe_load` y el alias `np.float`) se aplican al cargar el
modelo (`adapters/btc.py`), no sobre los archivos del clon.

`chords` necesita la salida del paso `tempo`: `{"beats": [segundos, ...]}`. Sin beats devuelve una
lista vacía y `key` devuelve `null`.

El test que corre BTC de verdad (`tests/test_btc_adapter.py`) se omite si no están instalados
torch y el clon. Para forzarlo: `$env:GUITAR_BTC_DIR = "<clon>"` y `pytest tests/test_btc_adapter.py`.

## Cifra Club

El worker no consulta Cifra Club (bloquea los pedidos automáticos, ADR 0012). Si Juan Pedro pegó la
cifra en la vista de la canción, el trabajo trae `cifra_text` (texto plano o HTML de la página) y el
paso `cifraclub` lo parsea y lo cruza con los acordes detectados. Sin texto, o si no se reconoce
ningún acorde, el análisis sigue sin ese cruce. Si cambia el texto, se rehacen ese paso y los que
dependen de él (la clave de caché lleva el hash del texto).

## Separación de pistas (acompañamiento sin guitarra)

Además de analizar, el worker atiende trabajos `separation` (la API los encola al terminar un
análisis). Pipeline: descarga (reusa el WAV en caché) -> Demucs `htdemucs_6s` en CPU -> mezcla de
todas las pistas menos la guitarra (una sola ganancia, pico <= -1 dBFS) -> m4a -> sube
`no_guitar` -> `result`. Las pistas y la mezcla quedan en `<cache>/<youtube_id>/` (`stems/`,
`no_guitar.wav`): una segunda corrida no vuelve a separar.

- Requiere el extra `separation` (`demucs`) y los pesos; `.\scripts\install.ps1` instala ambos. Los
  pesos van a `GUITAR_DEMUCS_MODEL_DIR` (por defecto `%USERPROFILE%\GuitarApp\models\demucs`).
- Tarda varios minutos por canción en CPU. Sin demucs o sin pesos, el trabajo falla (permanente)
  con un mensaje que manda a `install.ps1`; el análisis no se ve afectado.
- Los tests usan un separador falso; la separación real solo se prueba en tu PC.

## Tests

```powershell
cd worker
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```

El test de `tempo` con el modelo real (beat_this, clicks a BPM conocido) corre solo en local con el extra `analysis` y los pesos instalados; en la CI se omite.
