import { useEffect, useState } from 'react'

export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: T }

type Settled<T> =
  | { source: unknown; data: T; message?: undefined }
  | { source: unknown; data?: undefined; message: string }

/**
 * Carga datos al montar o cuando cambia `load` (pasarlo con useCallback).
 * Mientras el resultado guardado no corresponda al `load` actual, está cargando.
 */
export function useAsyncData<T>(
  load: (signal: AbortSignal) => Promise<T>,
): AsyncState<T> {
  const [settled, setSettled] = useState<Settled<T> | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal).then(
      (data) => setSettled({ source: load, data }),
      (error: unknown) => {
        if (controller.signal.aborted) return
        const message =
          error instanceof Error ? error.message : 'Error desconocido'
        setSettled({ source: load, message })
      },
    )
    return () => controller.abort()
  }, [load])

  if (settled?.source !== load) return { status: 'loading' }
  if (settled.message !== undefined)
    return { status: 'error', message: settled.message }
  return { status: 'ready', data: settled.data as T }
}
