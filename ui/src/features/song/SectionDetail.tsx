import type { ReactNode } from 'react'
import type { Notation } from '../../notation/types'
import type { SectionSync } from '../../backing/useBackingSync'
import { Fretboard } from '../../components/Fretboard/Fretboard'
import { Tab } from '../../components/Tab/Tab'
import { LowConfidenceLegend } from '../../components/LowConfidenceLegend/LowConfidenceLegend'
import { ChordDiagram } from '../../components/ChordDiagram/ChordDiagram'
import type { ChartSection, SongChartContent } from '../../songs/types'
import {
  chordTonic,
  formatTime,
  isLowConfidence,
  LOW_CONFIDENCE,
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
  activeIndex,
}: {
  cells: string[]
  accents: number[]
  label: string
  confidence: number
  activeIndex: number | null
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
          data-now={index === activeIndex ? 'true' : undefined}
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
  strumIndex,
}: {
  section: ChartSection
  instrument: Instrument
  strumIndex: number | null
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
          activeIndex={null}
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
          activeIndex={strumIndex}
        />
      </div>
    )
  }
  return <p className="page-note">Todavía no hay rasgueo para esta sección.</p>
}

function Riff({
  riff,
  activeIndices,
}: {
  riff: Notation
  activeIndices: readonly number[]
}) {
  return (
    <section className="song-riff" aria-label="Riff">
      <h4 className="song-subtitle">Riff</h4>
      <div className="song-riff__tab">
        <Tab
          notation={riff}
          activeIndices={activeIndices}
          lowConfidenceBelow={LOW_CONFIDENCE}
        />
      </div>
      <div className="song-riff__board">
        <Fretboard
          notation={riff}
          activeIndices={activeIndices}
          lowConfidenceBelow={LOW_CONFIDENCE}
        />
      </div>
      <LowConfidenceLegend notation={riff} below={LOW_CONFIDENCE} />
    </section>
  )
}

export function SectionDetail({
  section,
  instrument,
  sync = null,
  renderRiff = (view) => view,
}: {
  section: ChartSection
  instrument: Instrument
  /** Acorde y golpe que suenan ahora (si el acompañamiento está en esta sección). */
  sync?: SectionSync | null
  /** Envuelve la vista del riff (por ejemplo con el editor de tab). */
  renderRiff?: (view: ReactNode) => ReactNode
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
                data-now={index === sync?.chordIndex ? 'true' : undefined}
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
      <Playing
        section={section}
        instrument={instrument}
        strumIndex={sync?.strumIndex ?? null}
      />
      {renderRiff(
        section.riff && (
          <Riff riff={section.riff} activeIndices={sync?.riffIndices ?? []} />
        ),
      )}
    </article>
  )
}
