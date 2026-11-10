import { useCallback, useState } from 'react'
import { Fretboard } from '../../components/Fretboard/Fretboard'
import { LowConfidenceLegend } from '../../components/LowConfidenceLegend/LowConfidenceLegend'
import { Tab } from '../../components/Tab/Tab'
import type { PlaybackAudio } from '../../playback/clock'
import { usePlayback } from '../../playback/usePlayback'
import { LOW_CONFIDENCE } from '../song/chartView'
import { categoryLabel } from './categories'
import './ExerciseCard.css'
import { completeExercise, fetchExercise } from './studyApi'
import type { Completion, Exercise, Instrument } from './types'
import { useAsyncData } from './useAsyncData'

const NO_INDICES: readonly number[] = []
const singleIndex = (index: number | null): readonly number[] =>
  index === null ? NO_INDICES : [index]
const MIN_BPM = 20
const MAX_BPM_FLOOR = 240

export interface ExerciseCardProps {
  exercise: Exercise & { best_bpm?: number | null }
  /** Muestra el chip "en la sesión de hoy". */
  inTodaySession?: boolean
  /** Se llama después de registrar el Terminé en la API. */
  onCompleted?: (completion: Completion) => void
  /**
   * Evento que suena según el acompañamiento de una canción. Solo se usa cuando
   * el motor propio del ejercicio no está sonando (si no, manda el motor).
   */
  backingActiveIndices?: readonly number[]
  /** Solo para tests: audio inyectado (con identidad estable). */
  audio?: () => PlaybackAudio
}

const asInstrument = (value: string): Instrument =>
  value === 'classical' ? 'classical' : 'electric'

function Chips({
  exercise,
  best,
  bestFailed,
  inTodaySession,
}: {
  exercise: Exercise
  best: number | null | undefined
  bestFailed: boolean
  inTodaySession: boolean
}) {
  const reached =
    best != null && exercise.bpm_target != null && best >= exercise.bpm_target
  return (
    <div className="chips">
      {exercise.bpm_target != null && (
        <span className="chip">
          Objetivo <b>{exercise.bpm_target} bpm</b>
        </span>
      )}
      {best === undefined ? (
        <span className="chip">
          {bestFailed ? 'No se pudo cargar tu mejor marca' : 'Mejor marca…'}
        </span>
      ) : (
        <span className={`chip${reached ? ' chip--ok' : ''}`}>
          {best === null ? (
            'Sin marca todavía'
          ) : (
            <>
              Tu mejor <b>{best} bpm</b>
            </>
          )}
        </span>
      )}
      {inTodaySession && <span className="chip">En la sesión de hoy</span>}
    </div>
  )
}

export function ExerciseCard({
  exercise,
  inTodaySession = false,
  onCompleted,
  backingActiveIndices = NO_INDICES,
  audio,
}: ExerciseCardProps) {
  const { notation } = exercise
  const playback = usePlayback(notation, {
    bpm: exercise.bpm_start ?? notation.bpm,
    metronome: true,
    audio,
  })

  const knownBest = exercise.best_bpm
  const load = useCallback(
    (signal: AbortSignal): Promise<{ best_bpm: number | null }> =>
      knownBest === undefined
        ? fetchExercise(exercise.id, signal)
        : Promise.resolve({ best_bpm: knownBest }),
    [exercise.id, knownBest],
  )
  const detail = useAsyncData(load)
  const [recordedBest, setRecordedBest] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const loadedBest =
    detail.status === 'ready' ? detail.data.best_bpm : undefined
  const best = recordedBest ?? loadedBest

  async function finish() {
    setSaving(true)
    setSaveError(null)
    try {
      const completion = await completeExercise(
        exercise.id,
        playback.bpm,
        asInstrument(exercise.instrument),
      )
      setRecordedBest(completion.best_bpm)
      onCompleted?.(completion)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Error desconocido')
    } finally {
      setSaving(false)
    }
  }

  const engineRules = playback.isPlaying || playback.activeIndex !== null
  const activeIndices = engineRules
    ? singleIndex(playback.activeIndex)
    : backingActiveIndices
  const stepping = playback.mode === 'step'
  const maxBpm = Math.max(MAX_BPM_FLOOR, exercise.bpm_target ?? 0)

  return (
    <article className="exercise-card">
      <header className="exercise-card__head">
        <p className="exercise-card__category">
          {categoryLabel(exercise.category)}
        </p>
        <h3 className="display exercise-card__title">{exercise.title}</h3>
        <Chips
          exercise={exercise}
          best={best}
          bestFailed={detail.status === 'error'}
          inTodaySession={inTodaySession}
        />
      </header>

      {exercise.description && (
        <p className="exercise-card__description">{exercise.description}</p>
      )}

      <div className="exercise-card__board">
        <Fretboard
          notation={notation}
          activeIndices={activeIndices}
          lowConfidenceBelow={LOW_CONFIDENCE}
        />
      </div>
      <div className="exercise-card__tab">
        <Tab
          notation={notation}
          activeIndices={activeIndices}
          lowConfidenceBelow={LOW_CONFIDENCE}
        />
        <LowConfidenceLegend notation={notation} below={LOW_CONFIDENCE} />
      </div>

      <div className="exercise-card__transport">
        <button
          type="button"
          className="btn btn--primary"
          onClick={playback.isPlaying ? playback.pause : playback.play}
          aria-label={playback.isPlaying ? 'Pausar' : 'Reproducir'}
        >
          {playback.isPlaying ? '❚❚ Pausar' : '▶ Reproducir'}
        </button>
        <button
          type="button"
          className="btn"
          aria-pressed={stepping}
          onClick={() => playback.setMode(stepping ? 'auto' : 'step')}
        >
          Nota por nota
        </button>
        <button
          type="button"
          className="btn"
          onClick={playback.prev}
          disabled={!stepping}
        >
          ← Anterior
        </button>
        <button
          type="button"
          className="btn"
          onClick={playback.next}
          disabled={!stepping}
        >
          Siguiente →
        </button>
        <div className="exercise-card__tempo">
          <span>Tempo</span>
          <input
            type="range"
            aria-label="Tempo (bpm)"
            min={MIN_BPM}
            max={maxBpm}
            value={playback.bpm}
            onChange={(event) => playback.setBpm(Number(event.target.value))}
          />
          <output>{playback.bpm} bpm</output>
        </div>
      </div>

      <footer className="exercise-card__record">
        <button
          type="button"
          className="btn btn--primary"
          onClick={finish}
          disabled={saving}
        >
          Terminé
        </button>
        <p className="exercise-card__note">
          Guarda {playback.bpm} bpm como tu marca de este ejercicio.
        </p>
        {saveError && (
          <p className="study-status study-status--error" role="alert">
            No se pudo guardar: {saveError}
          </p>
        )}
      </footer>
    </article>
  )
}
