# 0017 — Transcripción de riffs: basic-pitch con modelo ONNX

- Fecha: 2026-11-02
- Estado: aceptada (provisoria hasta validar con guitarra real en la PC)
- Fase: 5

## Contexto

El worker tiene que pasar la pista `guitar` que deja Demucs a notas (onset, offset, altura) para armar el riff de cada sección (plan, § Pipeline paso 7). Restricción dura: instalar y correr en Windows 11 + Python 3.12 + CPU, sin PyTorch ni TensorFlow. Candidatos (elegidos por Juan Pedro): **basic-pitch** de Spotify y **pYIN de librosa** (solo monofónico, ya instalado).

Scripts, audio sintético y mediciones crudas: `spikes/riffs/` (README para reproducir).

**Aviso de alcance: todas las cifras son de audio sintético** (7 riffs generados con síntesis aditiva de cuerda pulsada, 48 kHz, notas conocidas), medidas en una máquina Linux x86-64 con CPU y Python 3.12, no en la PC con Windows. Una guitarra real, y más una pista separada por Demucs, es más difícil que esto: los números son un piso de comparación entre candidatos, no una promesa de calidad. La validación con riffs reales queda para la PC con `spikes/riffs/medir_audio_real.py`.

### Cómo se instaló basic-pitch (verificado)

basic-pitch 0.4.0 declara `tensorflow<2.15.1`, que no tiene wheels para Python 3.12. Se instaló con `pip install basic-pitch --no-deps` más `onnxruntime` y sus dependencias livianas (librosa, resampy, scipy, scikit-learn, pretty_midi, mir_eval, numpy). El paquete trae `basic_pitch/saved_models/icassp_2022/nmp.onnx`; `Model(ICASSP_2022_MODEL_PATH)` lo carga con onnxruntime y `predict()` corre sin TensorFlow (solo avisos de logging). Versiones usadas: basic-pitch 0.4.0, onnxruntime 1.31.1, librosa 1.0.0, mir_eval 0.8.2, numpy 2.5.4. No se pudo probar en Windows desde este entorno; onnxruntime y las demás tienen wheels `win_amd64` para cp312, por lo que se espera que ande igual.

### Los casos

| Caso | Qué tiene |
| --- | --- |
| `lento_penta_90` | pentatónica de La menor, corcheas a 90 bpm, 16 notas |
| `rapido_semicorcheas_140` | semicorcheas a 140 bpm (107 ms por nota), 32 notas |
| `power_chords` | 8 acordes de 3 voces (raíz, quinta, octava), 24 notas |
| `double_stops` | 8 dobles cuerdas (terceras y sextas), 16 notas |
| `ligados` | hammer-ons y pull-offs: ataque suave de 30 ms sin golpe de púa, 24 notas |
| `ruido_reverb_bajo` | el lento más ruido (SNR 20 dB), reverb corta y bajo de fondo a -14 dB (sangrado de Demucs) |
| `bends` | 6 notas con glissando de 1 o 2 semitonos; la verdad es la altura inicial |

Métrica: `mir_eval.transcription` con onset +-50 ms y altura exacta (tolerancia 50 cents sobre el semitono). "Con offsets" exige además que el offset caiga dentro del 20 % de la duración (mínimo 50 ms). P/R/F1 por caso.

## Mediciones

F1 sin offsets (con offsets entre paréntesis); basic-pitch con los umbrales elegidos (abajo). Tiempos de proceso por archivo (5 a 15 s de audio) en CPU, modelo ya cargado; **el primer pYIN del proceso tarda 11 s por la compilación JIT de numba**.

| Caso | Notas ref | basic-pitch F1 (offs.) | P / R | pYIN F1 (offs.) | P / R |
| --- | --- | --- | --- | --- | --- |
| lento_penta_90 | 16 | 0.97 (0.18) | 0.94 / 1.00 | **1.00 (0.94)** | 1.00 / 1.00 |
| rapido_semicorcheas_140 | 32 | **1.00 (0.00)** | 1.00 / 1.00 | 0.97 (0.94) | 1.00 / 0.94 |
| power_chords | 24 | **0.98 (0.90)** | 0.96 / 1.00 | 0.26 (0.19) | 0.57 / 0.17 |
| double_stops | 16 | **1.00 (1.00)** | 1.00 / 1.00 | 0.00 (0.00) | 0.00 / 0.00 |
| ligados | 24 | 0.98 (0.24) | 0.96 / 1.00 | **1.00 (0.96)** | 1.00 / 1.00 |
| ruido_reverb_bajo | 16 | 0.78 (0.54) | 0.64 / 1.00 | **0.89 (0.83)** | 0.80 / 1.00 |
| bends | 6 | 0.60 (0.00) | 0.43 / 1.00 | 0.55 (0.00) | 0.38 / 1.00 |
| **Promedio, los 7** | | **0.90 (0.41)** | 0.85 / 1.00 | 0.67 (0.55) | 0.68 / 0.73 |
| Promedio, 5 monofónicos | | 0.87 (0.19) | 0.79 / 1.00 | 0.88 (0.73) | 0.84 / 0.99 |
| Tiempo medio por archivo | | 0.45 s | | 0.60 s (11 s la primera vez) | |

Lecturas:

- **Polifonía**: pYIN no sirve (F1 0.00 en dobles cuerdas, 0.26 en power chords); basic-pitch las resuelve casi perfecto. Un riff con power chords o dobles cuerdas es normal en el repertorio, así que un transcriptor solo monofónico no alcanza.
- **Monofónico**: empatan en onsets (0.87 contra 0.88). pYIN es mucho mejor en offsets (0.73 contra 0.19) y algo más robusto con ruido, reverb y bajo de fondo (0.89 contra 0.78); basic-pitch agrega notas fantasma ahí (precisión 0.64).
- **Bends**: ninguno sirve. Los dos parten el glissando en escalones de semitono, que cuentan como notas de más (precisión 0.4). El bend hay que tratarlo como técnica a marcar a mano en el editor, no como algo que el transcriptor detecte.
- **Ligados**: ambos encuentran los onsets suaves (F1 0.98 y 1.00) aunque no haya golpe de púa.
- **Offsets de basic-pitch**: con onset 0.7 / frame 0.4 las notas salen acortadas o partidas y los offsets fallan. No importa: el worker cuantiza a la grilla y define la duración por el onset siguiente (F5-T05), y se desconfía del offset.
- **Tiempo**: ambos son bien menores a la duración del audio; ninguno limita.

### Barrido de umbrales de basic-pitch

Grilla de 27 combinaciones (`onset_threshold` 0.3/0.5/0.7, `frame_threshold` 0.2/0.3/0.4, `minimum_note_length` 58/80/127.7 ms), F1 promedio de los 7 casos sin offsets (`resultados/barrido.json`):

| onset | frame | min. ms | F1 | F1 con offsets |
| --- | --- | --- | --- | --- |
| 0.7 | 0.3 | 127.7 | 0.904 | 0.317 |
| 0.7 | 0.4 | 127.7 | 0.904 | 0.405 |
| **0.7** | **0.4** | **58** | 0.901 | **0.409** |
| 0.7 | 0.4 | 80 | 0.901 | 0.409 |
| 0.5 | 0.3 | 127.7 | 0.846 | 0.394 |
| 0.5 | 0.2 | 58 | 0.670 | 0.344 |
| 0.3 | 0.2 | 58 | 0.592 | 0.420 |

## Decisión

**basic-pitch con el modelo ONNX del paquete, solo.** Umbrales de partida: `onset_threshold=0.7`, `frame_threshold=0.4`, `minimum_note_length=58` ms. Se prefirió 58 ms a 127.7 ms (mismo F1, 0.904 contra 0.901) porque 127.7 ms es más largo que una semicorchea a 140 bpm (107 ms) y descartaría notas rápidas en audio real.

- Los umbrales son del sintético y 0.7 está en el borde de la grilla: con guitarra real, que ataca más suave, puede perder notas. `medir_audio_real.py --barrido` los reajusta; el worker los lee de configuración y no del código.
- El worker usa de basic-pitch onsets y alturas, y descarta sus offsets (duración = hasta el próximo onset o el fin del compás en la grilla). La confianza de cada nota sale de la amplitud que devuelve el modelo (campo `confidence`, F5-T02).
- Bends: no se detectan; quedan para el editor.

**No se combina con pYIN en esta versión.** La combinación (basic-pitch general, pYIN en pasajes monofónicos para mejores offsets) se evaluó con los números y no se justifica: en onsets, lo que importa, empatan en monofónico; los offsets ya se descartan; y sumar pYIN implica detectar qué pasajes son monofónicos, más una compilación JIT de 11 s en el primer uso, más una segunda segmentación casera. Se reabre solo si la validación real muestra muchas notas fantasma de basic-pitch en pasajes monofónicos, y entonces pYIN sirve para filtrar: descartar notas de basic-pitch sin f0 sonoro y coherente.

### Instalación en Windows 11 (PowerShell, Python 3.12, CPU)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install onnxruntime librosa resampy scipy scikit-learn pretty_midi mir_eval soundfile numpy
.\.venv\Scripts\python -m pip install basic-pitch --no-deps
.\.venv\Scripts\python -c "from basic_pitch.inference import ICASSP_2022_MODEL_PATH, Model; Model(ICASSP_2022_MODEL_PATH); print('ok')"
```

Al integrarlo al worker (F5-T05): `basic-pitch` va fijado en `==0.4.0` con `--no-deps` en `scripts/install.ps1` (un `pip install` normal intentaría traer `tensorflow<2.15.1` y fallaría), y las otras dependencias, en el `pyproject.toml` del worker. El modelo viaja dentro del paquete: no hace falta descargar nada.

## Alternativas consideradas

- **pYIN de librosa (solo)**: monofónico; F1 0.00 y 0.26 en dobles cuerdas y power chords. Descartado como transcriptor general; queda como posible filtro de confianza.
- **basic-pitch con TensorFlow/TFLite/CoreML**: no hay wheels de TensorFlow < 2.15.1 para Python 3.12; el modelo ONNX da el mismo resultado sin eso.
- **Combinación basic-pitch + pYIN**: ver Decisión; sin ganancia que lo justifique con estos números.
- **Detección de bends**: ninguno la resuelve; se marca a mano.
- No se midieron otros transcriptores (MT3, Omnizart, CREPE, etc.): requieren PyTorch/TensorFlow o modelos que no bajan sin acceso a Hugging Face, fuera de la restricción de instalación.

## Consecuencias

- Gana: transcripción polifónica en CPU, ~0.5 s por archivo corto, sin TensorFlow ni PyTorch, instalable con pip.
- Cuesta: la instalación con `--no-deps` es frágil (hay que fijar versiones y verificar al instalar); precisión del 90 % en sintético no se traduce a guitarra real y separada por Demucs.
- Vigilar: (1) validar en la PC con riffs reales y reajustar umbrales antes de fiarse de F5-T05; (2) notas fantasma con sangrado de otras pistas, por eso la confianza visible en la UI y el editor de tab (F5-T09/T10); (3) los avisos de logging de TensorFlow/CoreML al importar basic-pitch (se silencian); (4) si la validación real sale floja, reabrir este ADR con los números.

## Umbrales de secciones candidatas (F5-T05)

El worker transcribe solo las secciones candidatas (`domain/riff_candidates.py`): la intro y las de polifonía baja, con un mínimo de notas. Valores iniciales:

- `MIN_NOTES = 8`: notas mínimas (ataques dentro de la sección).
- `MAX_MEAN_POLYPHONY = 1.6`: notas simultáneas promedio por ataque; arriba de eso es rasgueo de acordes.
- `SIMULTANEOUS_WINDOW_S = 0.05`: ataques a menos de 50 ms cuentan como el mismo golpe.

**No están calibrados con audio real**: salen de razonar sobre el audio sintético del spike. Hay que ajustarlos con canciones de verdad (en la PC de Juan Pedro) antes de confiar en la selección.
