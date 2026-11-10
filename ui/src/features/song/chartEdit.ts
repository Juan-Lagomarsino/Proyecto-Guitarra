import type {
  ChordShapeOption,
  ChordShapePreferences,
  StrumPatternEntry,
} from '../../api/songs'
import type { ChartSection, SongChartContent } from '../../songs/types'

export interface SectionBounds {
  name: string
  start_s: number
  end_s: number
}

/** Qué impide guardar estos límites y nombre (mismas reglas que el esquema), o null si está bien. */
export function sectionProblem(
  content: SongChartContent,
  sectionId: string,
  { name, start_s, end_s }: SectionBounds,
): string | null {
  if (name.trim() === '') return 'La sección necesita un nombre.'
  if (!(start_s >= 0 && start_s < end_s))
    return 'El inicio tiene que ser menor que el fin.'
  const sections = [...content.sections].sort((a, b) => a.order - b.order)
  const index = sections.findIndex((s) => s.id === sectionId)
  const previous = sections[index - 1]
  const next = sections[index + 1]
  if (previous && start_s < previous.end_s)
    return `Se pisa con la sección ${previous.name}.`
  if (next && end_s > next.start_s)
    return `Se pisa con la sección ${next.name}.`
  const chords = sections[index]?.chords ?? []
  if (chords.some((c) => c.t_s < start_s || c.t_s >= end_s))
    return 'Hay acordes fuera de esos límites; movelos o ajustá los tiempos.'
  return null
}

export function replaceSection(
  content: SongChartContent,
  sectionId: string,
  patch: Partial<ChartSection>,
): SongChartContent {
  return {
    ...content,
    sections: content.sections.map((section) =>
      section.id === sectionId ? { ...section, ...patch } : section,
    ) as SongChartContent['sections'],
  }
}

const beatsPerBar = (timeSignature: string | undefined) =>
  Number((timeSignature ?? '4/4').split('/')[0])

/** Patrones elegibles: del tipo y del compás de la canción; el actual siempre se conserva. */
export function patternOptions(
  patterns: StrumPatternEntry[],
  kind: StrumPatternEntry['kind'],
  timeSignature: string | undefined,
  currentId: string | null,
): StrumPatternEntry[] {
  const beats = beatsPerBar(timeSignature)
  return patterns.filter(
    (p) => p.kind === kind && (p.beats_per_bar === beats || p.id === currentId),
  )
}

/** Campo de la sección (`strum` o `arpeggio`) para un patrón del catálogo, con confianza plena. */
export function withPattern(
  pattern: StrumPatternEntry,
): Pick<ChartSection, 'strum'> | Pick<ChartSection, 'arpeggio'> {
  if (pattern.kind === 'arpeggio')
    return {
      arpeggio: {
        pattern_id: pattern.id,
        pattern: pattern.pattern,
        confidence: 1,
      },
    }
  return {
    strum: {
      pattern: pattern.pattern,
      accent: pattern.accent,
      beats_per_cycle: pattern.beats_per_cycle,
      pattern_id: pattern.id,
      confidence: 1,
    },
  }
}

/** Trastes absolutos (con el capo sumado) de una forma; es la clave de las preferencias. */
export function shapeKey(shape: ChordShapeOption['shape'], capo: number) {
  return shape.map((fret) => (fret === 'x' ? 'x' : fret + capo)).join(',')
}

/** La forma de mayor peso en las preferencias que está entre las opciones, o null. */
export function preferredShape(
  preferences: ChordShapePreferences,
  instrument: string,
  chordName: string,
  capo: number,
  options: ChordShapeOption[],
): ChordShapeOption | null {
  const weights = preferences[instrument]?.[chordName] ?? {}
  const ranked = options
    .map((option) => ({
      option,
      weight: weights[shapeKey(option.shape, capo)] ?? 0,
    }))
    .filter(({ weight }) => weight > 0)
    .sort((a, b) => b.weight - a.weight)
  return ranked[0]?.option ?? null
}
