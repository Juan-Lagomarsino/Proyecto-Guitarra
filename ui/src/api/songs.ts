import { apiFetch, apiFetchWithStatus } from './client'

export type AnalysisStatus = 'queued' | 'processing' | 'ready' | 'error'
export type SongSource = 'youtube' | 'spotify' | 'search'

export interface SongSummary {
  id: number
  title: string | null
  artist: string | null
  source: SongSource
  analysis_status: AnalysisStatus
  current_step: string | null
  bpm: number | null
  key: string | null
  created_at: string
  url: string | null
  error: string | null
}

export interface SongDetail extends SongSummary {
  duration_s: number | null
  year: number | null
}

export type NewSong = { url: string } | { title: string; artist: string }

export interface CreatedSong {
  /** true si la canción ya estaba en la biblioteca (la API responde 200). */
  existed: boolean
  song: SongDetail
}

export const fetchSongs = (signal?: AbortSignal) =>
  apiFetch<SongSummary[]>('/songs', { signal })

export const fetchSong = (id: number, signal?: AbortSignal) =>
  apiFetch<SongDetail>(`/songs/${id}`, { signal })

export async function createSong(body: NewSong): Promise<CreatedSong> {
  const { status, data } = await apiFetchWithStatus<SongDetail>('/songs', {
    method: 'POST',
    body,
  })
  return { existed: status === 200, song: data }
}

export const reanalyzeSong = (id: number) =>
  apiFetch<unknown>(`/songs/${id}/reanalyze`, { method: 'POST' })
