import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchSongs, type SongSummary } from '../../api/songs'
import { errorText } from './analysis'

export const POLL_INTERVAL_MS = 3000

export type LibraryState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; songs: SongSummary[] }

export const isActive = (song: SongSummary) =>
  song.analysis_status === 'queued' || song.analysis_status === 'processing'

/**
 * Biblioteca de canciones. Mientras alguna esté en cola o procesando,
 * se refresca sola cada 3 s; se detiene al terminar y al desmontar.
 */
export function useSongLibrary() {
  const [state, setState] = useState<LibraryState>({ status: 'loading' })
  const mounted = useRef(true)

  const reload = useCallback(async () => {
    try {
      const songs = await fetchSongs()
      if (mounted.current) setState({ status: 'ready', songs })
    } catch (error) {
      // un refresco fallido no pisa una lista que ya se mostraba
      if (!mounted.current) return
      setState((prev) =>
        prev.status === 'ready'
          ? prev
          : { status: 'error', message: errorText(error) },
      )
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void reload()
    return () => {
      mounted.current = false
    }
  }, [reload])

  const hasActive = state.status === 'ready' && state.songs.some(isActive)

  useEffect(() => {
    if (!hasActive) return
    const timer = setInterval(() => void reload(), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [hasActive, reload])

  return { state, reload }
}
