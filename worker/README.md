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

## Tests

```powershell
cd worker
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```

El test de `tempo` con el modelo real (beat_this, clicks a BPM conocido) corre solo en local con el extra `analysis` y los pesos instalados; en la CI se omite.
