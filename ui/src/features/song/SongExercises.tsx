import { useCallback } from 'react'
import { fetchSongExercises, type SongSectionInfo } from '../../api/songs'
import { useBackingSync } from '../../backing/useBackingSync'
import type { SongChartContent } from '../../songs/types'
import type { Exercise } from '../study/types'
import { AsyncView } from '../study/AsyncView'
import { ExerciseCard } from '../study/ExerciseCard'
import { useAsyncData } from '../study/useAsyncData'
import './practice.css'

interface Props {
  songId: number
  /** Cambia cada vez que se crea un ejercicio, para volver a cargar la lista. */
  refreshKey: number
  /** Secciones guardadas: dan el inicio de cada ejercicio en la canción. */
  sections: SongSectionInfo[]
  /** Chart actual (beat_grid y bpm para pasar segundos a beats); `null` si no hay. */
  content: SongChartContent | null
}

/** La tarjeta de Estudio con el "suena ahora" del acompañamiento en el mástil y la tab. */
function SyncedExerciseCard({
  exercise,
  section,
  content,
}: {
  exercise: Exercise
  section: SongSectionInfo | undefined
  content: SongChartContent | null
}) {
  const sync = useBackingSync(content)
  const indices = section ? sync.eventIndices(exercise.notation, section) : []
  return <ExerciseCard exercise={exercise} backingActiveIndices={indices} />
}

/** Ejercicios armados desde las secciones de la canción, con la tarjeta de Estudio. */
export function SongExercises({
  songId,
  refreshKey,
  sections,
  content,
}: Props) {
  const load = useCallback(
    (signal: AbortSignal) => {
      void refreshKey
      return fetchSongExercises(songId, signal)
    },
    [songId, refreshKey],
  )
  const state = useAsyncData(load)
  return (
    <section className="song-exercises" aria-label="Tus ejercicios">
      <AsyncView state={state}>
        {(exercises) =>
          exercises.length === 0 ? null : (
            <>
              <h3 className="progress-subtitle">Tus ejercicios</h3>
              <div className="song-exercises__list">
                {exercises.map((exercise) => (
                  <SyncedExerciseCard
                    key={exercise.id}
                    exercise={exercise}
                    section={sections.find(
                      (s) => s.id === exercise.song_section_id,
                    )}
                    content={content}
                  />
                ))}
              </div>
            </>
          )
        }
      </AsyncView>
    </section>
  )
}
