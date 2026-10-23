import { apiFetch } from './client'

export interface SessionExercise {
  id: number
  title: string
  category: string
  minutes: number
  duration_min: number
  bpm_target: number | null
  completed_today: boolean
  description: string | null
}

export interface SessionBlock {
  category: string
  minutes: number
  exercises: SessionExercise[]
}

export interface TodaySession {
  /** YYYY-MM-DD */
  date: string
  seed: number
  status: string
  total_minutes: number
  blocks: SessionBlock[]
}

export const fetchTodaySession = (signal?: AbortSignal) =>
  apiFetch<TodaySession>('/sessions/today', { signal })

export const regenerateTodaySession = () =>
  apiFetch<TodaySession>('/sessions/today/regenerate', { method: 'POST' })
