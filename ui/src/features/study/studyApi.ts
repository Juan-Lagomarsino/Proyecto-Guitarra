import { apiFetch } from '../../api/client'
import type {
  Completion,
  ExerciseDetail,
  Instrument,
  Lesson,
  LessonSummary,
  Level,
} from './types'

export const fetchLevels = (signal?: AbortSignal) =>
  apiFetch<Level[]>('/levels', { signal })

export const fetchLessons = (levelId: number, signal?: AbortSignal) =>
  apiFetch<LessonSummary[]>(`/levels/${levelId}/lessons`, { signal })

export const fetchLesson = (lessonId: number, signal?: AbortSignal) =>
  apiFetch<Lesson>(`/lessons/${lessonId}`, { signal })

export const fetchExercise = (exerciseId: number, signal?: AbortSignal) =>
  apiFetch<ExerciseDetail>(`/exercises/${exerciseId}`, { signal })

export const completeExercise = (
  exerciseId: number,
  bpmLogrado: number,
  instrumento: Instrument,
) =>
  apiFetch<Completion>(`/exercises/${exerciseId}/complete`, {
    method: 'POST',
    body: { bpm_logrado: bpmLogrado, instrumento },
  })
