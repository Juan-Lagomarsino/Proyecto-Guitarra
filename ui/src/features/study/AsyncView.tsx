import type { ReactNode } from 'react'
import type { AsyncState } from './useAsyncData'

interface AsyncViewProps<T> {
  state: AsyncState<T>
  children: (data: T) => ReactNode
}

/** Resuelve los estados de carga y error; muestra `children` con los datos. */
export function AsyncView<T>({ state, children }: AsyncViewProps<T>) {
  if (state.status === 'loading')
    return (
      <p className="study-status" role="status">
        Cargando…
      </p>
    )
  if (state.status === 'error')
    return (
      <p className="study-status study-status--error" role="alert">
        No se pudo cargar: {state.message}
      </p>
    )
  return <>{children(state.data)}</>
}
