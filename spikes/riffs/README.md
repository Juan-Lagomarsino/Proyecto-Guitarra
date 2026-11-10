# Spike de transcripción de riffs (F5-T01)

Compara **basic-pitch** (modelo ONNX, sin TensorFlow) y **pYIN de librosa** sobre riffs sintéticos con verdad
conocida. Resultados y elección: `docs/adr/0017-transcripcion-de-riffs.md`. No es código de producción.

Los números son de **audio sintético** medido en una máquina Linux x86-64 con CPU, Python 3.12. La validación
con guitarra real (pista `guitar` de Demucs) se hace en la PC con `medir_audio_real.py`.

## Archivos

| Archivo | Qué hace |
| --- | --- |
| `sintetizar.py` | Genera 7 riffs (WAV 48 kHz + JSON con la verdad) en `salida/` (ignorado por git) |
| `transcribir.py` | Los dos candidatos (`basic_pitch_notas`, `pyin_notas`) y los umbrales elegidos |
| `metricas.py` | `mir_eval.transcription` (onset +-50 ms, altura exacta) y lectura de la referencia |
| `medir.py` | Mide los sintéticos (`resultados/medicion.json`); `--barrido` prueba la grilla de umbrales (`resultados/barrido.json`) |
| `medir_audio_real.py` | Lo mismo sobre un WAV real contra una referencia tuya |

## Reproducir (PowerShell, Windows 11, Python 3.12, CPU)

```powershell
cd spikes\riffs
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install basic-pitch --no-deps   # sin TensorFlow
.\.venv\Scripts\python medir.py             # tabla de los sintéticos
.\.venv\Scripts\python medir.py --barrido   # barrido de umbrales de basic-pitch
```

Comprobar que instala: `python -c "from basic_pitch.inference import ICASSP_2022_MODEL_PATH, Model; Model(ICASSP_2022_MODEL_PATH)"`
(debe cargar sin error; los avisos de TensorFlow/CoreML/TFLite son esperables y se silencian en `transcribir.py`).

## Medir con audio real

```powershell
.\.venv\Scripts\python medir_audio_real.py C:\ruta\guitar.wav riff.tsv
.\.venv\Scripts\python medir_audio_real.py C:\ruta\guitar.wav riff.json --desde 42.0 --hasta 50.5 --lista
.\.venv\Scripts\python medir_audio_real.py C:\ruta\guitar.wav riff.tsv --barrido
```

Formatos de la referencia (tiempos en segundos del WAV completo, `midi` entero; E2 = 40, A2 = 45, E4 = 64):

```text
# riff.tsv: onset  offset  midi   (tabs o espacios; '#' comenta)
42.000  42.310  57
42.333  42.650  60
```

```json
{ "notas": [{ "onset": 42.0, "offset": 42.31, "midi": 57 }] }
```

Con `--desde/--hasta` se recorta el WAV y la referencia al mismo tramo. Para anotar la referencia, tomá la tab del
riff, el bpm de la canción y el primer beat, y convertí cada nota a segundos (`beat * 60 / bpm`); con +-50 ms de
tolerancia alcanza una referencia hecha a mano. Con `--lista` se ven las notas estimadas al lado de las de
referencia. Devuelve P/R/F1 por candidato (sin y con offsets) y el tiempo de proceso; con `--barrido`, la misma
métrica para toda la grilla de umbrales de basic-pitch, para reajustarlos con guitarra real.
