import { useCallback } from 'react'
import { fetchSongExercises } from '../../api/songs'
import { AsyncView } from '../study/AsyncView'
import { ExerciseCard } from '../study/ExerciseCard'
import { useAsyncData } from '../study/useAsyncData'
import './practice.css'

interface Props {
  songId: number
  /** Cambia cada vez que se crea un ejercicio, para volver a cargar la lista. */
  refreshKey: number
}

/** Ejercicios armados desde las secciones de la canción, con la tarjeta de Estudio. */
export function SongExercises({ songId, refreshKey }: Props) {
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
                  <ExerciseCard key={exercise.id} exercise={exercise} />
                ))}
              </div>
            </>
          )
        }
      </AsyncView>
    </section>
  )
}
