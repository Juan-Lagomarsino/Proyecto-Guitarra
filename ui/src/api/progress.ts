import { apiFetch } from './client'

export interface LevelProgress {
  level_id: number
  slug: string
  position: number
  name: string
  completed: number
  total: number
}

export interface ProgressSummary {
  current_streak: number
  max_streak: number
  practiced_days: number
  levels: LevelProgress[]
  songs_in_progress: number
}

export interface CalendarDay {
  date: string
  count: number
}

export interface ProgressCalendar {
  days: CalendarDay[]
}

export const fetchProgressSummary = () =>
  apiFetch<ProgressSummary>('/progress/summary')

/** `from` y `to` en formato YYYY-MM-DD. */
export const fetchProgressCalendar = (from: string, to: string) =>
  apiFetch<ProgressCalendar>(
    `/progress/calendar?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  )
