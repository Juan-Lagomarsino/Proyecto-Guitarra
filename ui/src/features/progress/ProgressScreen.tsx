import { useEffect, useState } from 'react'
import {
  fetchProgressCalendar,
  fetchProgressSummary,
  type CalendarDay,
  type ProgressSummary,
} from '../../api/progress'
import { Heatmap } from './Heatmap'
import { yearRange } from './heatGrid'
import './progress.css'

interface Loaded {
  summary: ProgressSummary
  days: CalendarDay[]
  from: string
  to: string
}

const plural = (n: number, one: string, many: string) =>
  `${n} ${n === 1 ? one : many}`

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="progress-stat">
      <span className="progress-stat-value display">{value}</span>
      <span className="progress-stat-label">{label}</span>
    </div>
  )
}

export function ProgressScreen() {
  const [data, setData] = useState<Loaded | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const { from, to } = yearRange(new Date())
    let active = true
    Promise.all([fetchProgressSummary(), fetchProgressCalendar(from, to)])
      .then(([summary, calendar]) => {
        if (active) setData({ summary, days: calendar.days, from, to })
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <section className="page progress">
      <h2 className="display page-title">Progreso</h2>
      {failed && (
        <p role="alert" className="page-note">
          No pudimos cargar tu progreso. Probá de nuevo en un rato.
        </p>
      )}
      {!failed && !data && <p className="page-note">Cargando…</p>}
      {data && <ProgressContent data={data} />}
    </section>
  )
}

function ProgressContent({ data }: { data: Loaded }) {
  const { summary, days, from, to } = data
  return (
    <>
      {summary.practiced_days === 0 && (
        <p className="page-note">
          Todavía no practicaste nada. Cuando hagas tu primer ejercicio, tu
          racha y tu avance aparecen acá.
        </p>
      )}
      <div className="progress-stats">
        <Stat
          label="Racha actual"
          value={plural(summary.current_streak, 'día', 'días')}
        />
        <Stat
          label="Racha máxima"
          value={plural(summary.max_streak, 'día', 'días')}
        />
        <Stat label="Días practicados" value={String(summary.practiced_days)} />
      </div>
      <h3 className="progress-subtitle">Último año</h3>
      <Heatmap from={from} to={to} days={days} />
      <h3 className="progress-subtitle">Avance por nivel</h3>
      <ul className="progress-levels">
        {summary.levels.map((level) => (
          <li key={level.level_id} className="progress-level">
            <div className="progress-level-head">
              <span>{level.name}</span>
              <span>
                {level.completed}/{level.total}
              </span>
            </div>
            <progress
              className="progress-bar"
              max={level.total || 1}
              value={level.completed}
              aria-label={`Avance de ${level.name}`}
            />
          </li>
        ))}
      </ul>
    </>
  )
}
