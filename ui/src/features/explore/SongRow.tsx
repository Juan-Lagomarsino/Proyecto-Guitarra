import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  reanalyzeSong,
  type AnalysisStatus,
  type SongSummary,
} from '../../api/songs'
import { errorText, stepLabel } from './analysis'

interface SongRowProps {
  song: SongSummary
  highlighted: boolean
  onReanalyzed: () => void
}

function statusText(song: SongSummary): string {
  const labels: Record<AnalysisStatus, string> = {
    queued: 'En cola',
    processing: song.current_step
      ? `Procesando · ${stepLabel(song.current_step)}`
      : 'Procesando',
    ready: 'Lista',
    error: 'Error',
  }
  return labels[song.analysis_status]
}

export function SongRow({ song, highlighted, onReanalyzed }: SongRowProps) {
  const [retryProblem, setRetryProblem] = useState<string | null>(null)

  const retry = async () => {
    setRetryProblem(null)
    try {
      await reanalyzeSong(song.id)
      onReanalyzed()
    } catch (error) {
      setRetryProblem(errorText(error))
    }
  }

  const title = song.title ?? 'Analizando…'
  const subtitle = song.artist ?? (song.title === null ? song.url : null)
  const heading =
    song.analysis_status === 'ready' ? (
      <Link
        to={`/explorar/canciones/${song.id}`}
        className="explore-song__link"
      >
        {title}
      </Link>
    ) : (
      title
    )

  return (
    <li
      className="explore-song"
      data-highlighted={highlighted ? 'true' : undefined}
      data-status={song.analysis_status}
    >
      <div className="explore-song__main">
        <strong className="explore-song__title">{heading}</strong>
        <span className="explore-song__artist">{subtitle}</span>
        {song.analysis_status === 'error' && song.error && (
          <span className="explore-song__error">{song.error}</span>
        )}
      </div>
      <div className="explore-song__meta">
        <span className="explore-chip" data-status={song.analysis_status}>
          {statusText(song)}
        </span>
        {song.bpm !== null && (
          <span className="explore-song__fact">{Math.round(song.bpm)} BPM</span>
        )}
        {song.key && <span className="explore-song__fact">{song.key}</span>}
        {song.analysis_status === 'error' && (
          <button
            type="button"
            className="explore-retry"
            onClick={() => void retry()}
          >
            Reintentar
          </button>
        )}
      </div>
      {retryProblem && (
        <p role="alert" className="explore-problem">
          {retryProblem}
        </p>
      )}
    </li>
  )
}
