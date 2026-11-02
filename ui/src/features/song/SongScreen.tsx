import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../api/client'
import {
  fetchSong,
  fetchSongChart,
  type ChartInstrument,
  type SongDetail,
  type SongChartResponse,
  type SongSectionInfo,
} from '../../api/songs'
import type { SongChartContent } from '../../songs/types'
import { AsyncView } from '../study/AsyncView'
import { useAsyncData } from '../study/useAsyncData'
import { BackingProvider } from '../../backing/BackingContext'
import { useBackingSync } from '../../backing/useBackingSync'
import { BackingPanel } from './BackingPanel'
import { CifraPanel } from './CifraPanel'
import { PracticeSection } from './PracticeSection'
import { SectionDetail } from './SectionDetail'
import { RiffEditing } from './RiffEditing'
import { SectionEditing } from './SectionEditing'
import { SectionTimeline } from './SectionTimeline'
import { SongExercises } from './SongExercises'
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
): Promise<SongChartResponse | null> {
  try {
    return await fetchSongChart(id, instrument, signal)
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
      {song.analysis_status !== 'ready' && (
        <p className="song-header__status" role="status">
          {song.analysis_status === 'error'
            ? 'El último análisis falló.'
            : 'Reanalizando la canción…'}
        </p>
      )}
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

const CIFRA_UNUSED =
  'La cifra cargada no coincidió con lo que se escucha; se usaron los acordes detectados.'

/** La cifra está cargada y el análisis terminó, pero ninguna sección tomó sus acordes. */
function CifraUnusedNotice({
  song,
  content,
}: {
  song: SongDetail
  content: SongChartContent | null
}) {
  if (!song.has_cifra || song.analysis_status !== 'ready' || !content) {
    return null
  }
  if (content.sections.some((s) => s.chord_source === 'cifraclub')) return null
  return (
    <p className="song-cifra-unused" role="status">
      {CIFRA_UNUSED}
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

function Chart({
  song,
  initial,
  onCreated,
}: {
  song: SongDetail
  initial: SongChartResponse
  onCreated: () => void
}) {
  const [chart, setChart] = useState(initial)
  const content = chart.content
  const sections = timelineSections(content)
  const [selectedId, setSelectedId] = useState(sections[0]?.id ?? '')
  const [loopId, setLoopId] = useState<string | null>(null)
  const selected = sections.find((s) => s.id === selectedId) ?? sections[0]
  const sync = useBackingSync(content)
  if (!selected)
    return <p className="page-note">Esta canción todavía no tiene secciones.</p>
  const stored = song.sections.find((s) => s.slug === selected.id && !s.stale)
  return (
    <>
      <BackingPanel
        song={song}
        content={content}
        selected={selected}
        onLoopChange={setLoopId}
      />
      <SectionTimeline
        sections={sections}
        selectedId={selected.id}
        onSelect={setSelectedId}
        loopId={loopId}
        playingId={sync.activeSection?.id ?? null}
      />
      <Legend />
      <SectionEditing
        songId={song.id}
        chart={chart}
        section={selected}
        onChange={setChart}
      >
        <SectionDetail
          section={selected}
          instrument={content.instrument}
          sync={sync.forSection(selected)}
          renderRiff={(view) => (
            <RiffEditing
              songId={song.id}
              chart={chart}
              section={selected}
              onChange={setChart}
            >
              {view}
            </RiffEditing>
          )}
        />
      </SectionEditing>
      {stored && (
        <PracticeSection
          key={stored.id}
          songId={song.id}
          sectionId={stored.id}
          sectionName={selected.name}
          instrument={content.instrument}
          hasRiff={!!selected.riff}
          onCreated={onCreated}
        />
      )}
    </>
  )
}

function SongBody({
  song,
  onCifraChanged,
}: {
  song: SongDetail
  onCifraChanged: () => void
}) {
  const [instrument, setInstrument] = useState<ChartInstrument>('classical')
  const load = useCallback(
    (signal: AbortSignal) => loadChart(song.id, instrument, signal),
    [song.id, instrument],
  )
  const chart = useAsyncData(load)
  const content =
    chart.status === 'ready' ? (chart.data?.content ?? null) : null
  const stale = song.sections.filter((s) => s.stale)
  const [exercisesKey, setExercisesKey] = useState(0)

  return (
    <BackingProvider>
      <Header song={song} content={content} />
      <CifraUnusedNotice song={song} content={content} />
      <InstrumentSelector value={instrument} onChange={setInstrument} />
      <AsyncView state={chart}>
        {(data) =>
          data ? (
            <Chart
              key={`${song.id}-${instrument}`}
              song={song}
              initial={data}
              onCreated={() => setExercisesKey((key) => key + 1)}
            />
          ) : (
            <p className="page-note">
              Todavía no hay acordes de guitarra{' '}
              {instrument === 'classical' ? 'clásica' : 'eléctrica'} para esta
              canción.
            </p>
          )
        }
      </AsyncView>
      <SongExercises
        songId={song.id}
        refreshKey={exercisesKey}
        sections={song.sections}
        content={content}
      />
      <StaleSections sections={stale} />
      <CifraPanel
        songId={song.id}
        hasCifra={song.has_cifra}
        cifraUrl={song.cifra_url}
        onChanged={onCifraChanged}
      />
    </BackingProvider>
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
  const [fresh, setFresh] = useState<SongDetail | null>(null)
  const refresh = useCallback(async () => {
    try {
      setFresh(await fetchSong(songId))
    } catch {
      // si falla la recarga se queda con el detalle anterior
    }
  }, [songId])

  return (
    <section className="page song">
      <Link to="/explorar" className="study-back">
        ← Volver a Explorar
      </Link>
      <AsyncView state={detail}>
        {(song) => (
          <SongBody
            key={song.id}
            song={fresh?.id === song.id ? fresh : song}
            onCifraChanged={() => void refresh()}
          />
        )}
      </AsyncView>
    </section>
  )
}
