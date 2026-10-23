import type { Notation } from '../../notation/types'

export interface Level {
  id: number
  slug: string
  position: number
  name: string
  description: string
  instrument: string
}

export interface LessonSummary {
  id: number
  level_id: number
  slug: string
  position: number
  title: string
}

export interface Exercise {
  id: number
  lesson_id: number
  slug: string
  title: string
  type: string
  instrument: string
  category: string
  /** Texto plano corto de cómo practicarlo; la API lo manda o no. */
  description?: string | null
  bpm_start: number | null
  bpm_target: number | null
  duration_min: number
  notation: Notation
}

export interface ExerciseDetail extends Exercise {
  best_bpm: number | null
}

export interface Lesson extends LessonSummary {
  content_md: string
  exercises: Exercise[]
}

export type Instrument = 'classical' | 'electric'

export interface Completion {
  id: number
  exercise_id: number
  completed_at: string
  bpm_logrado: number
  instrumento: string
  best_bpm: number
}
