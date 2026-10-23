import type { CSSProperties } from 'react'
import { ChordDiagram } from '../../components/ChordDiagram/ChordDiagram'
import { Fretboard } from '../../components/Fretboard/Fretboard'
import type { ChordDiagramProps } from '../../components/ChordDiagram/ChordDiagram'
import type { Notation } from '../../notation/types'

/** La menor pentatónica, posición 1, con La como tónica. */
const SAMPLE: Notation = {
  bpm: 80,
  tonic: 'A',
  events: [
    { t: 0, dur: 1, string: 6, fret: 5 },
    { t: 1, dur: 1, string: 6, fret: 8 },
    { t: 2, dur: 1, string: 5, fret: 5 },
    { t: 3, dur: 1, string: 5, fret: 7 },
    { t: 4, dur: 1, string: 4, fret: 5 },
    { t: 5, dur: 1, string: 4, fret: 7 },
    { t: 6, dur: 1, string: 3, fret: 5 },
    { t: 7, dur: 1, string: 3, fret: 7 },
    { t: 8, dur: 1, string: 2, fret: 5 },
    { t: 9, dur: 1, string: 2, fret: 8 },
    { t: 10, dur: 1, string: 1, fret: 5 },
    { t: 11, dur: 1, string: 1, fret: 8 },
  ],
}

const CHORDS: { chord: ChordDiagramProps['chord']; tonic: string }[] = [
  { chord: { name: 'C', shape: ['x', 3, 2, 0, 1, 0] }, tonic: 'C' },
  { chord: { name: 'Am', shape: ['x', 0, 2, 2, 1, 0] }, tonic: 'A' },
  {
    chord: {
      name: 'F',
      shape: [1, 3, 3, 2, 1, 1],
      barre: { fret: 1, from_string: 6, to_string: 1 },
    },
    tonic: 'F',
  },
  {
    chord: {
      name: 'Bm',
      shape: [7, 9, 9, 7, 7, 7],
      barre: { fret: 7, from_string: 6, to_string: 1 },
    },
    tonic: 'B',
  },
]

interface ThemePreviewProps {
  theme: Record<string, string>
}

/** Vista previa: las variables del borrador se aplican solo a este bloque. */
export function ThemePreview({ theme }: ThemePreviewProps) {
  return (
    <section
      className="theme-preview"
      aria-label="Vista previa del tema"
      style={theme as CSSProperties}
    >
      <p className="theme-preview-title display">Vista previa</p>
      <p className="theme-preview-text">
        Así se ven el texto, el <em>acento</em> y el mástil.
      </p>
      <Fretboard notation={SAMPLE} activeIndex={3} />
      <div className="theme-preview-chords">
        {CHORDS.map(({ chord, tonic }) => (
          <ChordDiagram
            key={chord.name}
            chord={chord}
            tonic={tonic}
            size={96}
          />
        ))}
      </div>
    </section>
  )
}
