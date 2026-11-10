import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { BackingSource } from './types'

export interface BackingState {
  /** Fuente de acompañamiento activa, o `null` si todavía no se tocó play. */
  source: BackingSource | null
  /** Posición de la fuente en segundos de canción (se lee de la fuente). */
  position: number
}

const FALLBACK_POLL_MS = 100

const StateContext = createContext<BackingState>({ source: null, position: 0 })
interface BackingPublisher {
  setSource: (source: BackingSource | null) => void
  /** Publica la posición cuando no hay fuente viva (seek o loop en pausa, fuente retirada). */
  setPosition: (seconds: number) => void
}

const NOOP_PUBLISHER: BackingPublisher = {
  setSource: () => undefined,
  setPosition: () => undefined,
}

const PublishContext = createContext<BackingPublisher>(NOOP_PUBLISHER)

/** Llama a `fn` en cada cuadro (rAF; con intervalo si no existe); devuelve la baja. */
function onEachFrame(fn: () => void): () => void {
  if (typeof requestAnimationFrame !== 'function') {
    const id = setInterval(fn, FALLBACK_POLL_MS)
    return () => clearInterval(id)
  }
  let active = true
  let id = 0
  const loop = () => {
    if (!active) return
    fn()
    id = requestAnimationFrame(loop)
  }
  id = requestAnimationFrame(loop)
  return () => {
    active = false
    cancelAnimationFrame(id)
  }
}

/**
 * Reparte la fuente activa y su posición (para el resaltado de F3-T09).
 * La posición se conserva aunque la fuente se retire o esté en pausa.
 */
export function BackingProvider({ children }: { children: ReactNode }) {
  const [source, setSource] = useState<BackingSource | null>(null)
  const [position, setPosition] = useState(0)

  useEffect(() => {
    if (source === null) return undefined
    return onEachFrame(() => setPosition(source.position()))
  }, [source])

  const publisher = useMemo(() => ({ setSource, setPosition }), [])
  const state = useMemo(() => ({ source, position }), [source, position])
  return (
    <PublishContext.Provider value={publisher}>
      <StateContext.Provider value={state}>{children}</StateContext.Provider>
    </PublishContext.Provider>
  )
}

/** `{ source, position }` del acompañamiento activo. */
export const useBacking = (): BackingState => useContext(StateContext)

/** Solo para el panel: publica (o retira con `null`) la fuente activa. */
export const usePublishBacking = () => useContext(PublishContext)
