import { ChordDiagram } from '../../components/ChordDiagram/ChordDiagram'
import type { ChartSection, SongChartContent } from '../../songs/types'
import {
  chordTonic,
  formatTime,
  isLowConfidence,
  shapeKey,
  uniqueChords,
} from './chartView'

type Instrument = SongChartContent['instrument']

const CHORD_SOURCE_LABELS: Record<ChartSection['chord_source'], string | null> =
  {
    detected: null,
    cifraclub: 'Acordes de Cifra Club',
    user: 'Acordes corregidos por vos',
  }

const confidenceFlag = (confidence: number) =>
  isLowConfidence(confidence) ? 'low' : 'ok'

function Pattern({
  cells,
  accents,
  label,
  confidence,
}: {
  cells: string[]
  accents: number[]
  label: string
  confidence: number
}) {
  return (
    <div
      className="song-pattern"
      data-confidence={confidenceFlag(confidence)}
      role="group"
      aria-label={label}
    >
      {cells.map((cell, index) => (
        <span
          key={index}
          className="song-pattern__cell"
          data-accent={accents.includes(index) ? 'true' : undefined}
        >
          {cell}
        </span>
      ))}
    </div>
  )
}

function Playing({
  section,
  instrument,
}: {
  section: ChartSection
  instrument: Instrument
}) {
  const { arpeggio, strum } = section
  if (instrument === 'classical' && arpeggio) {
    return (
      <div>
        <h4 className="song-subtitle">Arpegio</h4>
        <Pattern
          cells={arpeggio.pattern.split('-')}
          accents={[]}
          label={`Arpegio ${arpeggio.pattern}`}
          confidence={arpeggio.confidence}
        />
      </div>
    )
  }
  if (strum) {
    return (
      <div>
        <h4 className="song-subtitle">Rasgueo</h4>
        <Pattern
          cells={strum.pattern.split('')}
          accents={strum.accent ?? []}
          label={`Rasgueo ${strum.pattern}`}
          confidence={strum.confidence}
        />
      </div>
    )
  }
  return <p className="page-note">Todavía no hay rasgueo para esta sección.</p>
}

export function SectionDetail({
  section,
  instrument,
}: {
  section: ChartSection
  instrument: Instrument
}) {
  const chords = section.chords ?? []
  const sourceLabel = CHORD_SOURCE_LABELS[section.chord_source]
  return (
    <article className="song-section" aria-label={`Sección ${section.name}`}>
      <header className="song-section__head">
        <h3 className="song-section__name">{section.name}</h3>
        <span className="song-section__time">
          {formatTime(section.start_s)} – {formatTime(section.end_s)}
        </span>
        {sourceLabel && <span className="song-badge">{sourceLabel}</span>}
      </header>

      {chords.length === 0 ? (
        <p className="page-note">No se detectaron acordes en esta sección.</p>
      ) : (
        <>
          <ul className="song-progression" aria-label="Progresión">
            {chords.map((chord, index) => (
              <li
                key={index}
                className="song-progression__chord"
                data-confidence={confidenceFlag(chord.confidence)}
              >
                {chord.name}
              </li>
            ))}
          </ul>
          <ul className="song-diagrams" aria-label="Diagramas de acordes">
            {uniqueChords(chords).map(({ chord, confidence }) => (
              <li
                key={shapeKey(chord)}
                className="song-diagrams__item"
                data-confidence={confidenceFlag(confidence)}
              >
                <ChordDiagram
                  chord={chord}
                  tonic={chordTonic(chord.name)}
                  size={112}
                />
              </li>
            ))}
          </ul>
        </>
      )}
      <Playing section={section} instrument={instrument} />
    </article>
  )
}
