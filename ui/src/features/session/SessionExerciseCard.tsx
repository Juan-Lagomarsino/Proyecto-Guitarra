import { useCallback } from 'react'
import type { SessionExercise } from '../../api/session'
import { AsyncView } from '../study/AsyncView'
import { ExerciseCard } from '../study/ExerciseCard'
import { fetchExercise } from '../study/studyApi'
import type { Completion } from '../study/types'
import { useAsyncData } from '../study/useAsyncData'

interface Props {
  exercise: SessionExercise
  onCompleted: (completion: Completion) => void
}

/** La sesión no trae la notación: se pide el ejercicio completo y se usa la tarjeta de Estudio. */
export function SessionExerciseCard({ exercise, onCompleted }: Props) {
  const load = useCallback(
    (signal: AbortSignal) => fetchExercise(exercise.id, signal),
    [exercise.id],
  )
  const state = useAsyncData(load)
  return (
    <AsyncView state={state}>
      {(detail) => (
        <ExerciseCard
          exercise={{ ...detail, description: exercise.description }}
          inTodaySession
          onCompleted={onCompleted}
        />
      )}
    </AsyncView>
  )
}
