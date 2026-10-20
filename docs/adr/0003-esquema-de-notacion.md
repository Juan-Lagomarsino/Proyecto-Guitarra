# 0003 — Esquema de notación

- Fecha: 2026-10-20
- Estado: aceptada
- Fase: 1

## Contexto

Todo lo que se toca (escalas, riffs, arpegios, acordes, rasgueos) se guarda en un único JSON que la UI renderiza como mástil y tablatura. El pipeline, el currículum y las correcciones producen el mismo formato. Hace falta una sola fuente de verdad, con validación en el backend y tipos en el frontend que no se desincronicen.

## Decisión

- **Fuente de verdad:** el modelo Pydantic `Notation` en `api/src/guitarra_api/domain/notation.py`. Los nombres de campo son los del plan, sin traducir (`tuning`, `bpm`, `time_signature`, `events[t, dur, string, fret, technique, bend]`, `chords[t, name, shape, barre]`, `strum[t, pattern, accent]`, `tonic`). Se rechazan campos desconocidos (`extra="forbid"`).
- **Export:** `api/scripts/export_notation_schema.py` escribe `schemas/notation.schema.json`. Un test (`test_committed_json_schema_matches_model`) falla si el archivo commiteado difiere del que genera el modelo. Para regenerar: `python api/scripts/export_notation_schema.py`.
- **Tipos TS:** `npm run gen:types` (en `ui/`) corre `json-schema-to-typescript` sobre el schema y escribe `ui/src/notation/types.ts`, que se commitea. Se desactivan los títulos autogenerados por campo para que los tipos no salgan como `String`, `Fret1`, etc.
- **Obligatorio y opcional:** solo `bpm` es obligatorio. `tuning` por defecto es la afinación estándar, `time_signature` por defecto `"4/4"`, `events`, `chords` y `strum` por defecto `[]`, `tonic` por defecto `null`. Justificación: una escala no tiene acordes ni rasgueo, un acorde suelto no tiene eventos; lo único que cualquier ejercicio necesita para reproducirse es el tempo.
- **Reglas de validación:**
  - `string` 1 a 6; `fret` 0 a 24; `t >= 0`; `dur > 0` (una nota de duración cero no tiene sentido); `bpm` en (0, 400].
  - `technique` en `h p / \ b r ~ pm x` o `null` (por defecto `null`).
  - `bend` (en tonos, `> 0`) es obligatorio si `technique == "b"` y está prohibido con cualquier otra técnica.
  - `tuning` tiene exactamente 6 notas con octava (`E2`, `Bb3`, `F#3`; octava 0 a 9). `tonic` es una nota sin octava (`A`, `C#`, `Bb`), en mayúscula y con un solo accidental.
  - `chords[].shape` tiene exactamente 6 elementos, cada uno `"x"` (cuerda muteada) o un traste 0 a 24.
  - `strum[].pattern` usa solo `D`, `U` y `-`; los índices de `accent` deben caer dentro del patrón.
  - `time_signature` con forma `N/M`.
- **Forma de `barre`:** `null` (sin cejilla) o `{"fret": 1..24, "from_string": 1..6, "to_string": 1..6}`, con `from_string > to_string` (de la cuerda más grave a la más aguda, p. ej. `6` a `1`). Es la forma mínima para dibujar la cejilla en el mástil; si la digitación necesita más (dedo, etc.) se amplía acá y en un solo lugar.

## Alternativas consideradas

- **Schema escrito a mano y modelos derivados:** se desincroniza del código de validación; el flujo inverso (modelo a schema) deja un solo origen.
- **Generar tipos TS con pydantic2ts:** exige tener Node y `json-schema-to-typescript` igual, y sumaría una dependencia Python; pasar por el JSON Schema commiteado también deja un artefacto revisable.
- **Hacer obligatorios `events`, `chords` y `strum`:** obligaría a escribir listas vacías en cada ejercicio sin aportar validación.

## Consecuencias

- Cambiar el formato implica tocar el modelo, correr el export y `npm run gen:types`; el test avisa si se olvida el export. No hay test automático para `types.ts` desactualizado (queda para CI si se quiere).
- `tuning` y `tonic` aceptan solo notación con `#` y `b`; si hiciera falta soportar dobles accidentales se amplía la expresión regular.
- Las técnicas de un evento con `r` (release) no exigen `bend`; el vínculo con el bend previo se interpreta en el render.
