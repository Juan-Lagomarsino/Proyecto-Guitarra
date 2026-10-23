import { useEffect, useRef } from 'react'
import type { CalendarDay } from '../../api/progress'
import { WEEKDAY_LABELS, buildWeeks, cellLabel } from './heatGrid'

interface HeatmapProps {
  from: string
  to: string
  days: CalendarDay[]
}

export function Heatmap({ from, to, days }: HeatmapProps) {
  const weeks = buildWeeks(from, to, days)
  const scrollRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollLeft = el.scrollWidth // arranca en lo más reciente
  }, [])
  return (
    <div className="heatmap-scroll" ref={scrollRef}>
      <div className="heatmap" role="group" aria-label="Días practicados">
        <div className="heatmap-weekdays" aria-hidden="true">
          <span className="heatmap-month" />
          {WEEKDAY_LABELS.map((label, i) => (
            <span key={label}>{i % 2 === 0 ? label : ''}</span>
          ))}
        </div>
        {weeks.map((week, w) => (
          <div className="heatmap-week" key={w}>
            <span className="heatmap-month" aria-hidden="true">
              {week.monthLabel}
            </span>
            {week.cells.map((cell, i) =>
              cell ? (
                <span
                  key={cell.date}
                  className={`heat-cell heat-${cell.level}`}
                  data-level={cell.level}
                  role="img"
                  aria-label={cellLabel(cell)}
                  title={cellLabel(cell)}
                />
              ) : (
                <span key={i} className="heat-cell heat-empty" />
              ),
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
