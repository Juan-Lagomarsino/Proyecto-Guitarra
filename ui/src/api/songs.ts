import type { Barre, ChartChord, SongChartContent } from '../songs/types'
import type { Exercise } from '../features/study/types'
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
  id: number
  slug: string
  name: string
  start_s: number
  end_s: number
  position: number
  /** Desapareció en un reanálisis pero conserva ejercicios. */
  stale: boolean
}

/** Asset de audio de la canción; `url` es relativa y sin token (ver `withToken`). */
export interface SongAudio {
  kind: 'original' | 'no_guitar' | (string & {})
  format: string
  url: string
}

export type SeparationStatus = 'none' | 'queued' | 'running' | 'done' | 'error'

export interface SongDetail extends SongSummary {
  duration_s: number | null
  year: number | null
  /** La API no devuelve el texto de la cifra, solo si hay. */
  has_cifra: boolean
  cifra_url: string | null
  sections: SongSectionInfo[]
  audio: SongAudio[]
  separation_status: SeparationStatus
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
/** Guarda el chart editado completo como versión de usuario (o devuelve la vigente si no cambió). */
export const saveUserChart = (
  id: number,
  instrument: ChartInstrument,
  content: SongChartContent,
) =>
  apiFetch<SongChartResponse>(`/songs/${id}/chart?instrument=${instrument}`, {
    method: 'PUT',
    body: content,
  })

/** Descarta la versión de usuario y devuelve el chart automático vigente. */
export const discardUserChart = (id: number, instrument: ChartInstrument) =>
  apiFetch<SongChartResponse>(
    `/songs/${id}/chart/user?instrument=${instrument}`,
    { method: 'DELETE' },
  )

/** Entrada del catálogo de rasgueos y arpegios (`GET /strum-patterns`). */
export interface StrumPatternEntry {
  id: string
  name: string
  kind: 'strum' | 'arpeggio'
  beats_per_bar: number
  style: string
  complexity: number
  pattern: string
  accent: number[]
  beats_per_cycle: number
}

export const fetchStrumPatterns = (signal?: AbortSignal) =>
  apiFetch<StrumPatternEntry[]>('/strum-patterns', { signal })

/** Forma de un acorde del diccionario (`GET /chords/shapes`), de la más fácil a la más difícil. */
export interface ChordShapeOption {
  name: string
  chord: string
  fallback: string | null
  difficulty: number
  shape: ChartChord['shape']
  barre: Barre | null
}

/** Con `capo`, `name` es el acorde que suena y las formas son las que se tocan con esa cejilla. */
export const fetchChordShapes = (
  name: string,
  capo = 0,
  signal?: AbortSignal,
) =>
  apiFetch<ChordShapeOption[]>(
    `/chords/shapes?name=${encodeURIComponent(name)}${capo ? `&capo=${capo}` : ''}`,
    { signal },
  )

/** Formas preferidas aprendidas: `{instrumento: {acorde: {trastes absolutos: peso}}}`. */
export type ChordShapePreferences = Record<
  string,
  Record<string, Record<string, number>>
>

export const fetchChordShapePreferences = (signal?: AbortSignal) =>
  apiFetch<ChordShapePreferences>('/preferences/chord-shapes', { signal })

export const reanalyzeSong = (id: number) =>
  apiFetch<unknown>(`/songs/${id}/reanalyze`, { method: 'POST' })

export type SectionExerciseType = 'chords' | 'strumming' | 'riff'

export const fetchSongExercises = (id: number, signal?: AbortSignal) =>
  apiFetch<Exercise[]>(`/songs/${id}/exercises`, { signal })

export const createSectionExercise = (
  songId: number,
  sectionId: number,
  type: SectionExerciseType,
  instrument: ChartInstrument,
) =>
  apiFetch<Exercise>(`/songs/${songId}/sections/${sectionId}/exercises`, {
    method: 'POST',
    body: { type, instrument },
  })
