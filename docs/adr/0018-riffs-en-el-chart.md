# 0018 — Riffs en el chart y confianza por evento

- Fecha: 2026-11-02
- Estado: aceptada
- Fase: 5

## Contexto

La Fase 5 transcribe riffs y melodías de la canción (worker) y los muestra como tab y mástil sincronizados con el acompañamiento (UI). Hace falta un lugar en el chart para guardarlos, un formato que no sea uno nuevo, y una forma de marcar lo dudoso de una transcripción automática. Ver ADR 0003 (notación) y 0008 (chart).

## Decisión

- **Riff = objeto `Notation`.** `ChartSection.riff: Notation | None = None`. Mismo formato que todo lo que se toca (eventos con `string`, `fret`, `technique`...). Los charts viejos no tienen `riff` y siguen validando.
- **Tiempos en beats relativos al inicio de la sección** (origen = `start_s`), la misma convención que los ejercicios de canción de la Fase 3 (`song_exercise.py`). El resto del chart sigue en segundos (ADR 0008); el riff es notación, y la notación va en beats.
- **Validación en `SongChartContent`**, porque necesita el chart entero: todo evento cumple `t + dur <= duración de la sección en beats` (+ 0,01 beats de tolerancia). La duración sale de `beat_grid` (`seconds_to_beats(end_s) - seconds_to_beats(start_s)`) o, sin grilla, de `(end_s - start_s) * bpm / 60` con el BPM del chart (`section_length_beats`). El `bpm` propio del riff no interviene en esta cuenta.
- **Riff vacío no se permite.** "Sin riff" es `null`; un riff con `events: []` es ambiguo (¿no se intentó o no hay nada?) y ensucia la UI. El worker omite el campo cuando no hay notas.
- **Afinación:** la de `Notation` (estándar por defecto); se puede indicar otra en `riff.tuning`.
- **`NoteEvent.confidence: float | None` en [0, 1]**, opcional: la notación escrita a mano no la lleva; las transcripciones automáticas sí, y la UI marca lo dudoso como en los acordes.
- Se regeneran `schemas/notation.schema.json`, `schemas/song_chart.schema.json` y los tipos TS (`npm run gen:types`).

## Alternativas consideradas

- **Riff en segundos (`t_s`) como los acordes:** obliga a convertir en cada uso y mezcla el formato de notación con otro; se descartó.
- **Riff como entidad aparte (tabla):** el chart se lee y versiona como un bloque (ADR 0008); un campo en la sección alcanza.
- **Confianza obligatoria:** rompería la notación existente y los ejercicios.

## Consecuencias

- El worker (que no importa la API) debe emitir el riff ya en beats relativos a la sección y sin pasarse del largo.
- Un cambio de BPM o grilla en un chart editado puede volver inválido un riff existente; el validador lo rechaza en el `PUT`.
- Mover los límites de una sección (editor de la Fase 2) también puede dejar un riff más largo que la sección: el `PUT` responde 422. El editor de tab (F5-T10) tiene que avisarlo con un mensaje claro o recortar el riff antes de guardar.
- El `bpm` del riff es obligatorio (lo hereda de `Notation`) pero no interviene en ninguna cuenta: quien arma un riff (worker o UI) copia siempre el `bpm` del chart.
