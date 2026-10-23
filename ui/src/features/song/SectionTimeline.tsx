import type { ChartSection } from '../../songs/types'
import { formatTime } from './chartView'

interface SectionTimelineProps {
  sections: ChartSection[]
  selectedId: string
  onSelect: (id: string) => void
}

/** Línea de tiempo: cada sección ocupa un ancho proporcional a su duración. */
export function SectionTimeline({
  sections,
  selectedId,
  onSelect,
}: SectionTimelineProps) {
  return (
    <ol className="song-timeline" aria-label="Secciones de la canción">
      {sections.map((section) => (
        <li
          key={section.id}
          className="song-timeline__item"
          style={{ flexGrow: Math.max(section.end_s - section.start_s, 1) }}
        >
          <button
            type="button"
            className="song-timeline__button"
            aria-pressed={section.id === selectedId}
            onClick={() => onSelect(section.id)}
          >
            <span className="song-timeline__name">{section.name}</span>
            <span className="song-timeline__time">
              {formatTime(section.start_s)}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
