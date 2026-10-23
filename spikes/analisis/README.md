# Spike de análisis (F2-T01)

Scripts descartables para elegir las herramientas de tempo, acordes, tonalidad y estructura.
El resultado y la elección están en `docs/adr/0006-herramientas-de-analisis.md`. No es código de producción.

## Reglas

- El audio (WAV) vive en la caché local `C:/Users/juanp/GuitarApp/cache/spike` (`CACHE` en `songs.py`), nunca en el repo.
  Ni los modelos (`*.ckpt`, `*.safetensors`, `*.pt`) ni el clon de BTC ni los plugins Vamp: todo va a esa caché.
- Las referencias de Cifra Club son fixtures en `worker/tests/fixtures/cifraclub/` (4 de 5; ver la nota de `cerca-del-fuego.json`).
- Los JSON de `resultados/` son las mediciones que cita el ADR.

## Reproducir (PowerShell, Python 3.12, CPU)

```powershell
cd spikes\analisis
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install beat-this librosa torch torchaudio --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
.\.venv\Scripts\python -m pip install yt-dlp mir_eval pyyaml safetensors soundfile scikit-learn
$env:FFMPEG_DIR = "<carpeta con ffmpeg.exe>"      # si ffmpeg no está en el PATH
.\.venv\Scripts\python descargar.py               # WAV 48 kHz a la caché
.\.venv\Scripts\python tempo.py beat_this librosa # resultados\tempo.json (madmom no instala: ver ADR)
.\.venv\Scripts\python acordes_plantillas.py      # línea base
# BTC: git clone --depth 1 https://github.com/jayg996/BTC-ISMIR19.git <CACHE>\btc ; luego:
.\.venv\Scripts\python acordes_btc.py voca ; .\.venv\Scripts\python acordes_btc.py majmin
# Chordino sin instalar nada: extraer los DLL del Vamp Plugin Pack y correr Sonic Annotator
.\.venv\Scripts\python extraer_vamp.py <Vamp.Plugin.Pack.Installer.exe> <CACHE>\vamp\plugins
.\.venv\Scripts\python acordes_chordino.py <CACHE>\vamp\plugins <sonic-annotator.exe>
.\.venv\Scripts\python parse_cifraclub.py         # HTML de la fixture -> JSON
.\.venv\Scripts\python evaluar_acordes.py         # resultados\acordes_metricas.json (todas las herramientas)
.\.venv\Scripts\python evaluar_compases.py ; .\.venv\Scripts\python tonalidad.py ; .\.venv\Scripts\python estructura.py
```

Notas: el host oficial del checkpoint de beat_this devolvió 503; `beat_this_checkpoint.py` lo reconstruye desde un espejo
safetensors. `bpm_*.py` consultan songbpm.com para el BPM de referencia (valores ya fijados en `songs.py`).
