# Worker de análisis

Corre nativo en Windows con Python 3.12 (venv en `worker/.venv`), nunca en Docker.

## Instalar y actualizar

`.\scripts\install.ps1` es idempotente: crea el venv, instala el worker, ffmpeg (winget) y llama a
`Update-YtDlp`, que hace `pip install -U yt-dlp` en el venv. YouTube cambia seguido; si una
descarga empieza a fallar, volvé a correr `.\scripts\install.ps1` antes de buscar otra causa.

## Tests

```powershell
cd worker
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```
