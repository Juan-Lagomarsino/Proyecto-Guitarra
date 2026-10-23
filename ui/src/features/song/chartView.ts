import type {
  ChartChord,
  ChartSection,
  Key,
  SongChartContent,
} from '../../songs/types'

/** Por debajo de este valor, la UI marca lo detectado como poco seguro. */
export const LOW_CONFIDENCE = 0.6

export const isLowConfidence = (confidence: number) =>
  confidence < LOW_CONFIDENCE

/** Secciones de la línea de tiempo, en el orden del chart. */
export const timelineSections = (content: SongChartContent): ChartSection[] =>
  [...content.sections].sort((a, b) => a.order - b.order)

export function formatTime(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const minutes = Math.floor(total / 60)
  const rest = String(total % 60).padStart(2, '0')
  return `${minutes}:${rest}`
}

export function keyLabel(key: Key | null | undefined): string | null {
  if (!key) return null
  return `${key.tonic} ${key.mode === 'major' ? 'mayor' : 'menor'}`
}

export const capoLabel = (capo: number | undefined) =>
  capo ? `Capo en ${capo}` : 'Sin capo'

/** Nota raíz del nombre de un acorde ("F#m7" -> "F#"). */
export const chordTonic = (name: string): string | undefined =>
  /^[A-G][#b]?/.exec(name)?.[0]

export interface UniqueChord {
  chord: ChartChord
  /** La menor confianza entre todas sus apariciones. */
  confidence: number
}

export const shapeKey = (chord: ChartChord) =>
  `${chord.name}|${chord.shape.join(',')}|${JSON.stringify(chord.barre ?? null)}`

/** Acordes distintos de una sección, en orden de aparición. */
export function uniqueChords(chords: ChartChord[]): UniqueChord[] {
  const found = new Map<string, UniqueChord>()
  for (const chord of chords) {
    const key = shapeKey(chord)
    const previous = found.get(key)
    found.set(key, {
      chord: previous?.chord ?? chord,
      confidence: Math.min(previous?.confidence ?? 1, chord.confidence),
    })
  }
  return [...found.values()]
}
