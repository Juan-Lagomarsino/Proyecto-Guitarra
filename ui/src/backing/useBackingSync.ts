import { useMemo } from 'react'
import type { Notation } from '../notation/types'
import type { ChartSection, SongChartContent } from '../songs/types'
import { useBacking } from './BackingContext'
import {
  activeChordIndex,
  activeEventIndices,
  activeSection,
  activeStrumIndex,
  sectionBeat,
} from './sync'

export interface SectionSync {
  chordIndex: number | null
  strumIndex: number | null
}

export interface BackingSync {
  /** Sección que suena ahora, o `null` si no hay posición válida. */
  activeSection: ChartSection | null
  /** Acorde y golpe que suenan en `section`; `null` si el audio no está en ella. */
  forSection: (section: ChartSection) => SectionSync | null
  /**
   * Índices de `notation.events` que suenan, con la notación contada desde el
   * inicio de `range` (los ejercicios de sección empiezan en el beat 0 de la sección).
   */
  eventIndices: (
    notation: Notation,
    range: { start_s: number; end_s: number },
  ) => number[]
}

/**
 * Combina la posición del acompañamiento con el chart. Todo sale de la
 * posición de la fuente (nada se cuenta), así que con loop el resaltado vuelve solo.
 */
export function useBackingSync(content: SongChartContent | null): BackingSync {
  const { source, position } = useBacking()
  // Sin fuente y en 0 todavía no se tocó nada: no se marca la primera sección.
  const hasPosition = source !== null || position > 0
  return useMemo(() => {
    const grid = content?.beat_grid
    const bpm = content?.bpm ?? 0
    const signature = content?.time_signature
    return {
      activeSection:
        hasPosition && content
          ? activeSection(position, content.sections)
          : null,
      forSection: (section) => {
        if (!hasPosition) return null
        const beat = sectionBeat(position, section, grid, bpm)
        if (beat === null) return null
        return {
          chordIndex: activeChordIndex(position, section.chords),
          strumIndex: section.strum
            ? activeStrumIndex(beat, section.strum, signature)
            : null,
        }
      },
      eventIndices: (notation, range) => {
        if (!hasPosition) return []
        const beat = sectionBeat(position, range, grid, bpm)
        return beat === null ? [] : activeEventIndices(notation, beat)
      },
    }
  }, [content, position, hasPosition])
}
