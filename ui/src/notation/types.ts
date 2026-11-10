/* Generado desde schemas/notation.schema.json con npm run gen:types. No editar a mano. */

export interface Notation {
  /**
   * @minItems 6
   * @maxItems 6
   */
  tuning?: [string, string, string, string, string, string]
  bpm: number
  time_signature?: string
  events?: NoteEvent[]
  chords?: Chord[]
  strum?: Strum[]
  tonic?: string | null
}
export interface NoteEvent {
  t: number
  dur: number
  string: number
  fret: number
  technique?: ('h' | 'p' | '/' | '\\' | 'b' | 'r' | '~' | 'pm' | 'x') | null
  bend?: number | null
  confidence?: number | null
}
export interface Chord {
  t: number
  name: string
  /**
   * @minItems 6
   * @maxItems 6
   */
  shape: [
    number | 'x',
    number | 'x',
    number | 'x',
    number | 'x',
    number | 'x',
    number | 'x',
  ]
  barre?: Barre | null
}
/**
 * Cejilla: traste y rango de cuerdas, de la más grave (6) a la más aguda (1).
 */
export interface Barre {
  fret: number
  from_string: number
  to_string: number
}
export interface Strum {
  t: number
  pattern: string
  accent?: number[]
}
