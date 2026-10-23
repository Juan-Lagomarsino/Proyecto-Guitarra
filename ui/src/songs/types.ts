/* Generado desde schemas/song_chart.schema.json con npm run gen:types. No editar a mano. */

export interface SongChartContent {
  instrument: 'classical' | 'electric'
  key?: Key | null
  bpm: number
  bpm_confidence?: number | null
  time_signature?: string
  capo?: number
  beat_grid?: BeatGrid | null
  /**
   * @minItems 1
   */
  sections: [ChartSection, ...ChartSection[]]
  sources?: SourceStep[]
}
export interface Key {
  tonic: string
  mode: 'major' | 'minor'
  confidence: number
}
/**
 * Instante (en segundos) de cada beat y del primer tiempo de cada compás.
 */
export interface BeatGrid {
  /**
   * @minItems 2
   */
  beats_s: [number, number, ...number[]]
  downbeats_s?: number[]
}
export interface ChartSection {
  id: string
  name: string
  start_s: number
  end_s: number
  order: number
  chord_source: 'detected' | 'cifraclub' | 'user'
  chords?: ChartChord[]
  strum?: SectionStrum | null
  arpeggio?: SectionArpeggio | null
}
/**
 * Acorde con el mismo `name`, `shape` y `barre` que la notación; `t_s` en segundos.
 */
export interface ChartChord {
  t_s: number
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
  confidence: number
}
/**
 * Cejilla: traste y rango de cuerdas, de la más grave (6) a la más aguda (1).
 */
export interface Barre {
  fret: number
  from_string: number
  to_string: number
}
/**
 * Rasgueo propuesto: un patrón que se repite, con el patrón del catálogo del que salió.
 */
export interface SectionStrum {
  pattern: string
  accent?: number[]
  beats_per_cycle?: number | null
  pattern_id: string
  confidence: number
}
/**
 * Arpegio p-i-m-a (solo guitarra clásica), p. ej. `p-i-m-a-m-i`.
 */
export interface SectionArpeggio {
  pattern_id: string
  pattern: string
  confidence: number
}
/**
 * Un paso del pipeline que corrió: qué herramienta y qué versión.
 */
export interface SourceStep {
  step: string
  tool: string
  version: string
}
