import { useCallback, useEffect, useState } from 'react'
import {
  fetchTodaySession,
  regenerateTodaySession,
  type TodaySession,
} from '../../api/session'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; session: TodaySession }

function assertSession(session: TodaySession): TodaySession {
  if (!Array.isArray(session?.blocks))
    throw new Error('la respuesta no tiene el formato esperado')
  return session
}

const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : 'Error desconocido'

export function useTodaySession() {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [regenerating, setRegenerating] = useState(false)
  const [regenerateError, setRegenerateError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchTodaySession(controller.signal)
      .then(assertSession)
      .then(
        (session) => setState({ status: 'ready', session }),
        (error: unknown) => {
          if (controller.signal.aborted) return
          setState({ status: 'error', message: messageOf(error) })
        },
      )
    return () => controller.abort()
  }, [])

  const regenerate = useCallback(async () => {
    setRegenerating(true)
    setRegenerateError(null)
    try {
      const session = assertSession(await regenerateTodaySession())
      setState({ status: 'ready', session })
    } catch (error) {
      setRegenerateError(messageOf(error))
    } finally {
      setRegenerating(false)
    }
  }, [])

  return { state, regenerating, regenerateError, regenerate }
}
