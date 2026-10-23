import type { SongChartContent } from '../songs/types'
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

export interface SongSectionInfo {
  slug: string
  name: string
  start_s: number
  end_s: number
  position: number
  /** Desapareció en un reanálisis pero conserva ejercicios. */
  stale: boolean
}

export interface SongDetail extends SongSummary {
  duration_s: number | null
  year: number | null
  /** La API no devuelve el texto de la cifra, solo si hay. */
  has_cifra: boolean
  cifra_url: string | null
  sections: SongSectionInfo[]
}

export interface CifraInput {
  text: string
  url: string | null
}

export interface CifraSaved extends SongSummary {
  /** false si ya había un análisis activo: la cifra se guardó igual. */
  reanalysis_queued: boolean
}

export type ChartInstrument = 'classical' | 'electric'

export interface SongChartResponse {
  song_id: number
  instrument: ChartInstrument
  version: number
  origin: 'auto' | 'cifraclub' | 'user'
  confidence: number | null
  content: SongChartContent
  created_at: string
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

export const fetchSongChart = (
  id: number,
  instrument: ChartInstrument,
  signal?: AbortSignal,
) =>
  apiFetch<SongChartResponse>(`/songs/${id}/chart?instrument=${instrument}`, {
    signal,
  })

export async function createSong(body: NewSong): Promise<CreatedSong> {
  const { status, data } = await apiFetchWithStatus<SongDetail>('/songs', {
    method: 'POST',
    body,
  })
  return { existed: status === 200, song: data }
}

export const saveCifra = (id: number, body: CifraInput) =>
  apiFetch<CifraSaved>(`/songs/${id}/cifra`, { method: 'PUT', body })

export const deleteCifra = (id: number) =>
  apiFetch<void>(`/songs/${id}/cifra`, { method: 'DELETE' })

export const reanalyzeSong = (id: number) =>
  apiFetch<unknown>(`/songs/${id}/reanalyze`, { method: 'POST' })
