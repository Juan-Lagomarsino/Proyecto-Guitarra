# 0008 — Esquema del chart de canción

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El worker produce, por canción e instrumento, un análisis (tonalidad, tempo, secciones, acordes, rasgueo, arpegio) con confianza por campo; la UI lo muestra, marca en otro color lo dudoso y lo deja editar; y el usuario puede pisarlo. Hace falta un único contenido validado en el backend, con tipos TS que no se desincronicen, y un modelo de datos que soporte versiones, cola de trabajos y ejercicios que salen de una sección. Sigue el patrón de la notación (ADR 0003).

## Decisión

- **Fuente de verdad:** `SongChartContent` en `api/src/guitarra_api/domain/song_chart.py` (Pydantic, `extra="forbid"`, nombres en inglés). Export con `api/scripts/export_song_chart_schema.py` a `schemas/song_chart.schema.json`; tipos TS con `npm run gen:types` (ahora genera notación y canciones) en `ui/src/songs/types.ts`. `test_committed_json_schema_matches_model` falla si el schema commiteado quedó viejo.
- **Forma:** `instrument`, `key {tonic, mode, confidence}`, `bpm`, `bpm_confidence`, `time_signature`, `capo` (0 a 12), `beat_grid?` (`beats_s[]`, `downbeats_s[]`), `sections[]` y `sources[]` (`{step, tool, version}` de cada paso que corrió). Cada sección: `id` estable (`^[a-z0-9][a-z0-9_-]*$`), `name`, `start_s`, `end_s`, `order`, `chord_source` (`detected`, `cifraclub`, `user`), `chords[]` (`t_s`, `name`, `shape`, `barre`, `confidence`), `strum` y `arpeggio` opcionales.
- **Reuso de notación:** `ChartChord` y `SectionStrum` reutilizan los tipos de campo de `notation.py` (`ChordName`, `ChordShape`, `Barre`, `StrumPattern`, `StrumAccents`) y la regla de acentos, pero **no heredan `t`**, para no mezclar unidades; el JSON y el schema de notación no cambian. `SectionStrum`: `pattern`, `accent`, `pattern_id`, `confidence` y `beats_per_cycle?` (cuántos beats dura el patrón); no tiene tiempo porque es un patrón que se repite. Un arpegio p-i-m-a (`SectionArpeggio`: `pattern_id`, `pattern` como `p-i-m-a-m-i`, `confidence`) solo es válido en charts de guitarra clásica.
- **Tiempo en segundos, no en beats:** todo el tiempo del chart (`start_s`, `end_s`, `t_s` de los acordes) está en segundos desde el inicio de la canción. Las grabaciones no van a click y el tempo deriva, así que un único BPM no alcanza para pasar a beats sin desfasar, y la Fase 3 tiene que sincronizar con el audio. Para pasar a beats (p. ej. T18, sección a notación) está `beat_grid` y la función pura `seconds_to_beats(t_s, beat_grid)`: interpola linealmente entre beats (el primer beat es 0) y extrapola con el primer o último intervalo. `beat_grid` es opcional y se valida: `beats_s` estrictamente creciente con al menos 2 beats, `downbeats_s` creciente y cada uno coincide con un beat (tolerancia 10 ms), y el primer beat no pasa del final de la última sección (el chart no guarda la duración de la canción).
- **Validaciones:** `start_s < end_s`; secciones sin solaparse, ordenadas por tiempo y con `order` estrictamente creciente; ids de sección únicos; acordes (`t_s`) dentro de `[start_s, end_s)` y ordenados; toda confianza en 0 a 1; `capo` 0 a 12; `bpm` en (0, 400]; al menos una sección.
- **Confianza obligatoria en cada acorde, rasgueo y arpegio.** Lo que edita el usuario va con `confidence: 1`. La confianza global (columna de `song_charts`) se calcula como el promedio simple de todas las confianzas del contenido (`overall_confidence`); es un indicador para ordenar y mostrar, no una métrica estadística.
- **Base de datos (migración `0003`):**
  - `songs` (`youtube_id` y `spotify_id` únicos y nullables, `analysis_status` con check), `song_sections` (con `slug` = id de la sección en el chart, para enlazar ambos mundos; único por canción), `song_charts` (única por `(song_id, instrument, version)`, `content` JSONB), `audio_assets`, `analysis_jobs`, `corrections`.
  - `song_charts.content` se valida con `SongChartContent` al asignarlo (validador del ORM) y el repositorio persiste la forma normalizada (`model_dump(mode="json")`).
  - `analysis_jobs` lleva `status`, `attempts`, `max_attempts`, `error`, `claimed_by`, `lease_until` y `current_step`, `finished_at` y `updated_at`, con un índice `(status, lease_until)` para el claim y el vencimiento de leases. El tipo de trabajo es texto libre (`analyze` por defecto) para que T03 y T04 sumen tipos sin migrar.
  - `exercises.lesson_id` pasa a nullable; se suma `song_section_id` con FK y el check `lesson_xor_song_section`. Las filas existentes tienen `lesson_id`, así que cumplen el check. El downgrade borra los ejercicios de canción (no existen en 0002) antes de volver a `NOT NULL`. **El downgrade es destructivo**: pierde esos ejercicios (y, al borrar las tablas, canciones, charts y trabajos); no usarlo con datos de canciones que importen.
- **Chart vigente:** el de mayor versión con origen `user` si existe; si no, el de mayor versión de los demás orígenes (`auto`, `cifraclub`). Así un reanálisis (`auto` nuevo) no pisa la edición del usuario.
- **Estados de la cola con nombre `status`**, igual que en `practice_sessions`, y valores en inglés (`queued`, `running`, `done`, `error`).

## Alternativas consideradas

- **Tiempos de acorde en beats:** obliga a tener la grilla para validar y para reproducir; el audio ya está en segundos. Se descartó.
- **Tablas relacionales para acordes y rasgueos:** el chart se lee y se escribe entero y se versiona como un bloque; JSONB validado es más simple y mantiene un solo formato.
- **Un solo `lesson_id` genérico con tipo de dueño:** pierde la FK real. Se prefirieron dos FK nullables con un check XOR.
- **Confianza global ponderada:** sin datos reales todavía; se deja el promedio simple y se cambia en un solo lugar (`overall_confidence`) si el uso lo pide.

## Consecuencias

- Cambiar el chart implica tocar el modelo, correr el export y `npm run gen:types`; el test avisa si se olvida el export (no hay test para `types.ts`).
- Los charts viejos se conservan por versión; borrar una canción borra en cascada secciones, charts, activos, trabajos y correcciones.
- El worker y la UI consumen `SongChartContent`; la API debe validar `POST /jobs/{id}/result` con el mismo modelo (T04).
- Los números 0006 y 0007 quedan reservados para T01 (herramientas de análisis y Demucs).
