# Fase 5 — Riffs y aprendizaje

Estado: **en curso** (plan aprobado por Juan Pedro el 2026-11-02)
Referencia: `docs/PLAN.md` § Pipeline de análisis (paso 7, Riffs), § Cómo "aprende", § Formato interno de notación, § Modelo de datos (`SongChart`, `Correction`), § UI y diseño (tablatura, confianza en otro color). La Fase 4 (Rig) queda afuera de esta sesión: necesita la PC.

## Criterios de aceptación de la fase (del plan)

1. Transcripción de riffs a tablatura en secciones candidatas, con confianza visible.
2. Editor de tab en la UI; las correcciones actualizan las preferencias de digitación.
3. Una canción nueva usa las posiciones preferidas aprendidas (test con datos de ejemplo).

## Decisiones de partida (se registran como ADR en la tarea indicada)

- **Los riffs salen de la pista de guitarra de Demucs** (la de la Fase 3), no de la mezcla: el trabajo de separación, después de armar la mezcla sin guitarra, transcribe la pista `guitar` en las secciones candidatas y manda los riffs en su resultado. Sin Demucs no hay riffs (el resto de la app sigue igual).
- **Transcripción → notas con tiempo y confianza → cuantización a la grilla de beats → digitación → formato de notación.** Cada paso es puro y testeable salvo el adaptador del modelo.
- **Secciones candidatas:** la intro y las secciones con pocas notas simultáneas (polifonía media baja) y suficientes notas; umbrales en un solo lugar, ajustables.
- **Digitación por programación dinámica** en `guitarra_core` (lo usan worker y API): minimiza saltos de mano, cambios de cuerda y estiramientos, con un término de preferencia aprendida. Pura, sin I/O.
- **Esquema:** la sección del chart suma `riff` (un objeto de notación: eventos con tiempo en beats relativos al inicio de la sección, igual que los ejercicios de la Fase 3) y el evento de notación suma `confidence` opcional (0–1). Cambio en un solo lugar, JSON Schema y tipos TS regenerados. — ADR en T02.
- **La versión del usuario gana por sección:** un riff corregido por el usuario nunca se pisa; si el usuario editó solo acordes, el riff automático nuevo igual se muestra.
- **Preferencias aprendidas:** tabla propia (`fingering_preferences`: por altura → cuerda/traste preferidos y zona de mano, con contadores). Se actualizan en el `PUT` del chart comparando el riff automático con el corregido (función pura en `guitarra_core`). El worker las recibe en el claim y las pasa a la digitación.
- **Formas de acorde preferidas (entran, por decisión de Juan Pedro):** en la vista de canción se puede elegir la forma de cada acorde (abierta, con cejilla, power chord, otra posición) de las que da `guitarra_core.chord_shapes`; esa elección se guarda en la versión del usuario y alimenta una preferencia por acorde (y por instrumento) que el análisis siguiente usa al elegir la forma. Tareas T12 y T13.
- **Fuera de alcance:** arpegios para clásica transcritos, detección de técnicas (bends, slides): el usuario las agrega en el editor.

### Decisiones de Juan Pedro al aprobar (2026-11-02)

- Spike con **basic-pitch y pYIN**; se elige midiendo (ADR en T01).
- **Sin Demucs no hay riffs automáticos** (se pueden cargar a mano en el editor).
- **Entran las formas de acorde preferidas** (T12, T13).

## Lo que la nube no tiene (y cómo se cubre)

| Falta | Impacto | Qué se hace acá | Qué queda para tu PC |
| --- | --- | --- | --- |
| Demucs real (pesos bloqueados) y canciones (YouTube bloqueado) | No hay pistas de guitarra reales | Riffs sintéticos (cuerdas pulsadas tipo Karplus-Strong con notas conocidas) para medir la transcripción y testear el pipeline | Correr el spike con 2–3 riffs reales tuyos y comparar con una tab de referencia |
| Docker Hub (429) | Sin compose | API nativa + Postgres local, E2E con `scripts/e2e-nativo.sh` | `docker compose up` y `scripts/e2e.ps1` |

Lo que **sí** anda acá: PyPI, así que el modelo de transcripción se puede instalar y correr de verdad sobre audio sintético.

## Tareas

| Id | Ola | Objetivo | Depende de | Estado |
| --- | --- | --- | --- | --- |
| F5-T01 | 0 | Spike: elegir el transcriptor midiendo con riffs sintéticos; script para medir con riffs reales en la PC | — | hecha (con audio sintético; validación real en la PC) |
| F5-T02 | 0 | Esquema: `confidence` en eventos de notación y `riff` por sección del chart | — | hecha |
| F5-T03 | 0 | Core: digitación por programación dinámica con preferencias | — | hecha |
| F5-T04 | 1 | Core: aprender preferencias de un par (automático, corregido) | T03 | hecha |
| F5-T05 | 1 | Worker: transcripción, secciones candidatas y cuantización a la grilla | T01, T02 | hecha |
| F5-T06 | 1 | API: riffs en el resultado de la separación, mezcla por sección con la versión del usuario | T02 | pendiente |
| F5-T07 | 2 | API: preferencias de digitación (tabla, actualización en el `PUT` del chart, envío en el claim) | T04, T06 | pendiente |
| F5-T08 | 2 | Worker: armado de riffs (digitación con preferencias → notación) y envío en el resultado | T03, T05, T06 | pendiente |
| F5-T09 | 2 | UI: riff por sección con tab y mástil, confianza visible, sincronizado con el acompañamiento | T02 | pendiente |
| F5-T10 | 3 | UI: editor de tab (traste, cuerda, técnica, duración, agregar y borrar) que guarda la versión del usuario | T09, T06 | pendiente |
| F5-T12 | 1 | Core + API: preferencias de forma de acorde (aprender de la versión del usuario, guardar, mandar en el claim) | — | hecha |
| F5-T13 | 2 | UI: elegir la forma de un acorde; worker: usar la forma preferida al armar el chart | T12 | pendiente |
| F5-T11 | 4 | Cierre: test de punta a punta de "canción nueva usa lo aprendido", E2E, guía para la PC, README | todas | pendiente |

### F5-T01 — Spike de transcripción

- **Archivos:** `spikes/riffs/` (scripts y notas), `docs/adr/0017-transcripcion-de-riffs.md`.
- **Qué:** generar 6–8 riffs sintéticos con notas conocidas (monofónicos, con double stops, rápidos a 140 bpm, con ruido de fondo leve) y comparar candidatos instalables en Windows + Python 3.12 en CPU: **basic-pitch** (el modelo ONNX viene dentro del paquete; se instala sin TensorFlow, con `onnxruntime`), **pYIN de librosa** (ya instalado, solo monofónico). Medir precisión/recall de notas (onset ±50 ms, altura exacta) con `mir_eval`, tiempo y si instala limpio. Dejar un script para correr lo mismo sobre audio real con una tab de referencia en la PC.
- **Criterio:** ADR con la tabla de mediciones, la elección y lo descartado.

### F5-T02 — Esquema

- **Archivos:** `api/src/guitarra_api/domain/notation.py` (`NoteEvent.confidence` opcional 0–1), `song_chart.py` (`ChartSection.riff: Notation | None`), JSON Schemas en `schemas/`, tipos TS generados, ADR `0018-riffs-en-el-chart.md`.
- **Criterio:** validación con casos válidos e inválidos (confianza fuera de rango, riff con eventos fuera de la duración de la sección en beats); tests de "esquema commiteado al día"; charts viejos sin `riff` siguen validando.

### F5-T03 — Digitación

- **Archivos:** `core/src/guitarra_core/fingering.py`.
- **Criterio:** dada una secuencia de notas (alturas MIDI, simultáneas o no), afinación y capo, devuelve cuerda/traste por nota; tests: escala que se queda en una posición, salto de octava que cambia de zona solo si conviene, notas simultáneas en cuerdas distintas y con estiramiento ≤ 4 trastes, nota fuera de rango → error claro, cuerdas al aire con costo configurable, y que una preferencia fuerte (p. ej. "La 4 en la 5.ª cuerda, traste 0" o "zona del traste 5") cambie la digitación elegida.

### F5-T04 — Aprendizaje de preferencias

- **Archivos:** `core/src/guitarra_core/fingering_preferences.py`.
- **Criterio:** función pura que, dado el riff automático y el corregido (eventos con altura, cuerda y traste), devuelve los ajustes a las preferencias (por altura → posición elegida, y zona de mano) solo donde el usuario cambió cuerda/traste para la misma altura; acumulación con decaimiento o tope para que una sola corrección no domine; serialización estable para guardarla. Tests de borde: notas agregadas o borradas, cambio de altura (no es una preferencia de digitación), corrección que vuelve a la automática.

### F5-T05 — Transcripción en el worker

- **Archivos:** `worker/.../adapters/transcriber.py` (el elegido en T01, import perezoso), `worker/.../domain/riff_candidates.py`, `domain/quantize.py`, extra en `pyproject.toml`, `install.ps1`.
- **Criterio:** tests con audio sintético (si el modelo está instalado, se corre de verdad acá; si no, se saltea) y con notas falsas: secciones candidatas por polifonía y cantidad de notas; cuantización a semicorchea o tresillo según el error menor, sin superponer notas de la misma cuerda; confianza por nota.

### F5-T06 — Riffs en la API

- **Archivos:** `application/job_queue.py`, `http/job_schemas.py`, servicio de charts.
- **Criterio:** el `result` de una separación acepta `riffs` opcional (`{section_id: Notation}`); se guarda una versión `auto` nueva de cada chart con los riffs; en `GET chart`, por sección, el riff del usuario gana y, si el usuario no tocó el riff de esa sección, se ve el automático aunque haya una versión de usuario por acordes; tests de todo eso y de riffs de secciones que ya no existen (se ignoran).

### F5-T07 — Preferencias en la API

- **Archivos:** modelo y migración `fingering_preferences`, servicio, `PUT /songs/{id}/chart` actualiza preferencias cuando cambia un riff, `GET /fingering/preferences` (UI, para mostrarlas) y `fingering_preferences` en el claim del worker.
- **Criterio:** tests: corregir un riff actualiza las preferencias con la función de T04; el claim las trae; borrar la versión del usuario no borra lo aprendido.

### F5-T08 — Armado de riffs en el worker

- **Archivos:** `worker/.../steps/riffs.py`, registro en el pipeline de separación.
- **Criterio:** con notas falsas: usa la digitación de core con las preferencias del claim, arma la notación por sección (beats relativos al inicio, confianza por evento), valida con el esquema y la manda en el `result`; sin pista de guitarra o sin candidatas, manda sin riffs y no falla.

### F5-T09 — Riff en la UI

- **Archivos:** `ui/src/features/song/` (bloque "Riff" en `SectionDetail`), `Tab` y `Fretboard` con estado de baja confianza (token CSS existente de la Fase 2 o uno nuevo `--low-confidence`), leyenda.
- **Skill:** `frontend-design`.
- **Criterio:** tab y mástil del riff de la sección, notas de baja confianza en otro color con leyenda, resaltado sincronizado con el acompañamiento (reusa la sincronía de la Fase 3); "Practicar esta sección" ofrece el tipo riff; tests; 375 px.

### F5-T10 — Editor de tab

- **Archivos:** `ui/src/features/song/RiffEditor.tsx` (+ lógica pura de edición).
- **Criterio:** elegir una nota y cambiar traste, cuerda (la altura se recalcula), técnica y duración; agregar y borrar notas; deshacer; guardar crea la versión del usuario (`PUT chart`) y muestra "editado por vos"; volver a la automática; tests de la lógica pura y del componente con la API mockeada; 375 px.

### F5-T12 — Preferencias de forma de acorde

- **Archivos:** `core/src/guitarra_core/chord_preferences.py` (pura: de un par de charts automático/usuario, qué forma eligió el usuario para cada acorde y por instrumento), tabla `chord_shape_preferences` y migración, actualización en el `PUT` del chart, `chord_shape_preferences` en el claim del análisis.
- **Criterio:** tests: cambiar la forma de un acorde guarda la preferencia (acorde + instrumento → forma); cambiar el nombre del acorde no cuenta como preferencia de forma; el claim la trae.

### F5-T13 — Elegir y usar la forma preferida

- **Archivos:** UI: en la edición de acordes de la Fase 2, selector de forma con los diagramas de las alternativas (`ChordDiagram`); worker: `core/instrument.py` / `steps/assemble.py` reciben las preferencias y, si hay una para el acorde, la usan antes de la regla por defecto (sin romper la regla de capo de clásica).
- **Criterio:** tests de UI (elegir otra forma y guardar) y de worker/core (con preferencia, el acorde sale con la forma preferida; sin preferencia, igual que antes).

### F5-T11 — Cierre

- **Archivos:** test de integración (API + core, con datos de ejemplo): corregir un riff de la canción A → claim de la canción B trae las preferencias → la digitación de B usa las posiciones aprendidas; lo mismo con una forma de acorde. E2E (resultado grabado con riff, ver confianza, editar una nota, guardar). `docs/fases/fase-5/validacion-en-pc.md`, README.
- **Criterio:** criterios de la fase uno por uno con evidencia, marcando lo que solo se verifica en tu PC.

## Orden de ejecución

1. Ola 0 en paralelo: T01, T02, T03.
2. Ola 1 en paralelo: T04, T05, T06, T12.
3. Ola 2 en paralelo: T07, T08, T09, T13.
4. Ola 3: T10. Ola 4: T11 y cierre.
