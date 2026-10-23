import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { TodaySession } from '../../api/session'
import { categoryLabel } from '../study/categories'
import { SessionExerciseCard } from './SessionExerciseCard'
import { formatSessionDate } from './formatDate'
import { useTodaySession } from './useTodaySession'
import './session.css'

const doneIdsOf = (session: TodaySession) =>
  session.blocks.flatMap((block) =>
    block.exercises.filter((e) => e.completed_today).map((e) => e.id),
  )

const totalOf = (session: TodaySession) =>
  session.blocks.reduce((sum, block) => sum + block.exercises.length, 0)

function EmptySession() {
  return (
    <p className="page-note">
      No hay ejercicios para hoy todavía. Pasá por{' '}
      <Link to="/estudio">Estudio</Link> y empezá por donde quieras.
    </p>
  )
}

function SessionBody({ session }: { session: TodaySession }) {
  const [localDone, setLocalDone] = useState<Set<number>>(new Set())
  const done = new Set([...doneIdsOf(session), ...localDone])
  const markDone = (id: number) => setLocalDone((prev) => new Set(prev).add(id))

  if (session.blocks.length === 0) return <EmptySession />

  return (
    <>
      <p className="session-summary" aria-live="polite">
        {done.size} de {totalOf(session)} hechos
      </p>
      {session.blocks.map((block) => (
        <section className="session-block" key={block.category}>
          <h3 className="display session-block__title">
            {categoryLabel(block.category)}
            <span className="session-block__minutes">{block.minutes} min</span>
          </h3>
          <div className="session-block__cards">
            {block.exercises.map((exercise) => (
              <div className="session-item" key={exercise.id}>
                {done.has(exercise.id) && (
                  <p className="session-item__done">✓ Hecho hoy</p>
                )}
                <SessionExerciseCard
                  exercise={exercise}
                  onCompleted={() => markDone(exercise.id)}
                />
              </div>
            ))}
          </div>
        </section>
      ))}
    </>
  )
}

export function TodayScreen() {
  const { state, regenerating, regenerateError, regenerate } = useTodaySession()
  const session = state.status === 'ready' ? state.session : null

  return (
    <section className="page session">
      <header className="session-head">
        <div>
          <h2 className="display page-title">Sesión de hoy</h2>
          {session && (
            <p className="session-meta">
              {formatSessionDate(session.date)} · {session.total_minutes} min
            </p>
          )}
        </div>
        <button
          type="button"
          className="btn"
          onClick={regenerate}
          disabled={regenerating || state.status === 'loading'}
        >
          {regenerating ? 'Regenerando…' : 'Regenerar'}
        </button>
      </header>
      {regenerateError && (
        <p className="study-status study-status--error" role="alert">
          No se pudo regenerar: {regenerateError}
        </p>
      )}
      {state.status === 'loading' && (
        <p className="study-status" role="status">
          Cargando…
        </p>
      )}
      {state.status === 'error' && (
        <p className="study-status study-status--error" role="alert">
          No se pudo cargar la sesión: {state.message}
        </p>
      )}
      {session && <SessionBody key={session.seed} session={session} />}
    </section>
  )
}
