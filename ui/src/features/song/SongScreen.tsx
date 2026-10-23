import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  fetchSong,
  fetchSongChart,
  type ChartInstrument,
  type SongDetail,
  type SongSectionInfo,
} from '../../api/songs'
import type { SongChartContent } from '../../songs/types'
import { AsyncView } from '../study/AsyncView'
import { useAsyncData } from '../study/useAsyncData'
import { SectionDetail } from './SectionDetail'
import { SectionTimeline } from './SectionTimeline'
import {
  capoLabel,
  keyLabel,
  LOW_CONFIDENCE,
  timelineSections,
} from './chartView'
import './song.css'

const INSTRUMENTS: { value: ChartInstrument; label: string }[] = [
  { value: 'classical', label: 'Clásica' },
  { value: 'electric', label: 'Eléctrica' },
]

/** null = todavía no hay chart de ese instrumento (404). */
async function loadChart(
  id: number,
  instrument: ChartInstrument,
  signal: AbortSignal,
): Promise<SongChartContent | null> {
  try {
    return (await fetchSongChart(id, instrument, signal)).content
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

function Header({
  song,
  content,
}: {
  song: SongDetail
  content: SongChartContent | null
}) {
  const bpm = content?.bpm ?? song.bpm
  const key = keyLabel(content?.key) ?? song.key
  return (
    <header className="song-header">
      <h2 className="display page-title">{song.title ?? 'Sin título'}</h2>
      {song.artist && <p className="song-header__artist">{song.artist}</p>}
      <dl className="song-facts">
        {bpm !== null && bpm !== undefined && (
          <div className="song-fact">
            <dt>BPM</dt>
            <dd>{Math.round(bpm)}</dd>
          </div>
        )}
        {key && (
          <div className="song-fact">
            <dt>Tonalidad</dt>
            <dd>{key}</dd>
          </div>
        )}
        {content && (
          <div className="song-fact">
            <dt>Capo</dt>
            <dd>{capoLabel(content.capo)}</dd>
          </div>
        )}
      </dl>
    </header>
  )
}

function InstrumentSelector({
  value,
  onChange,
}: {
  value: ChartInstrument
  onChange: (instrument: ChartInstrument) => void
}) {
  return (
    <div className="song-instruments" role="group" aria-label="Guitarra">
      {INSTRUMENTS.map(({ value: option, label }) => (
        <button
          key={option}
          type="button"
          className="explore-mode"
          aria-pressed={option === value}
          onClick={() => onChange(option)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function Legend() {
  return (
    <p className="song-legend">
      <span className="song-legend__swatch" aria-hidden="true" />
      Baja confianza (menos de {Math.round(LOW_CONFIDENCE * 100)} %): conviene
      revisarlo de oído.
    </p>
  )
}

function StaleSections({ sections }: { sections: SongSectionInfo[] }) {
  if (sections.length === 0) return null
  return (
    <section className="song-stale" aria-label="Secciones anteriores">
      <h3 className="progress-subtitle">Secciones anteriores</h3>
      <p className="page-note">
        Ya no aparecen en el último análisis, pero tienen ejercicios tuyos.
      </p>
      <ul className="song-stale__list">
        {sections.map((section) => (
          <li key={section.slug} className="song-stale__item">
            {section.name}
          </li>
        ))}
      </ul>
    </section>
  )
}

function Chart({ content }: { content: SongChartContent }) {
  const sections = timelineSections(content)
  const [selectedId, setSelectedId] = useState(sections[0]?.id ?? '')
  const selected = sections.find((s) => s.id === selectedId) ?? sections[0]
  if (!selected)
    return <p className="page-note">Esta canción todavía no tiene secciones.</p>
  return (
    <>
      <SectionTimeline
        sections={sections}
        selectedId={selected.id}
        onSelect={setSelectedId}
      />
      <Legend />
      <SectionDetail section={selected} instrument={content.instrument} />
    </>
  )
}

function SongBody({ song }: { song: SongDetail }) {
  const [instrument, setInstrument] = useState<ChartInstrument>('classical')
  const load = useCallback(
    (signal: AbortSignal) => loadChart(song.id, instrument, signal),
    [song.id, instrument],
  )
  const chart = useAsyncData(load)
  const content = chart.status === 'ready' ? chart.data : null
  const stale = song.sections.filter((s) => s.stale)

  return (
    <>
      <Header song={song} content={content} />
      <InstrumentSelector value={instrument} onChange={setInstrument} />
      <AsyncView state={chart}>
        {(data) =>
          data ? (
            <Chart key={`${song.id}-${instrument}`} content={data} />
          ) : (
            <p className="page-note">
              Todavía no hay acordes de guitarra{' '}
              {instrument === 'classical' ? 'clásica' : 'eléctrica'} para esta
              canción.
            </p>
          )
        }
      </AsyncView>
      <StaleSections sections={stale} />
    </>
  )
}

export function SongScreen() {
  const { id } = useParams()
  const songId = Number(id)
  const load = useCallback(
    (signal: AbortSignal) => fetchSong(songId, signal),
    [songId],
  )
  const detail = useAsyncData(load)

  return (
    <section className="page song">
      <Link to="/explorar" className="study-back">
        ← Volver a Explorar
      </Link>
      <AsyncView state={detail}>
        {(song) => <SongBody key={song.id} song={song} />}
      </AsyncView>
    </section>
  )
}
