import type { Notation } from '../../notation/types'
import { beatsPerBar, buildColumns, stringName } from './columns'
import type { Tuning } from './columns'
import {
  ANNOTATION_Y,
  LEFT_GUTTER,
  NOTE_BOX_HEIGHT,
  SYSTEM_CHROME,
  SYSTEM_HEIGHT,
  annotationX,
  layoutSystem,
  stringY,
} from './layout'
import type { PositionedColumn, SystemLayout } from './layout'
import { partitionSystems } from './systems'
import { useContainerWidth } from './useContainerWidth'

export interface TabProps {
  notation: Notation
  /** Índice en `notation.events` del evento que suena; resalta toda su columna. */
  activeIndex?: number | null
  /** Índices que suenan a la vez (un acorde); si viene, manda sobre `activeIndex`. */
  activeIndices?: readonly number[]
  /** Ancho en px. Si falta, se mide el contenedor. */
  width?: number
}

const STANDARD_TUNING: Tuning = ['E2', 'A2', 'D3', 'G3', 'B3', 'E4']
const FALLBACK_WIDTH = 640
const STRINGS = [1, 2, 3, 4, 5, 6]
const FONT = { fontFamily: 'var(--font-mono)' } as const

function buildLabel(notation: Notation): string {
  const count = notation.events?.length ?? 0
  const noun = count === 1 ? 'nota' : 'notas'
  return `Tablatura de guitarra con ${count} ${noun} a ${notation.bpm} bpm`
}

function StringsAndNames({
  layout,
  tuning,
}: {
  layout: SystemLayout
  tuning: Tuning
}) {
  return (
    <>
      {STRINGS.map((string) => (
        <g key={string}>
          <line
            data-role="string-line"
            x1={LEFT_GUTTER}
            x2={layout.endX}
            y1={stringY(string)}
            y2={stringY(string)}
            stroke="var(--line)"
            strokeWidth={1.2}
          />
          <text
            data-role="string-name"
            x={3}
            y={stringY(string) + 4}
            fontSize={10}
            fill="var(--muted)"
            style={FONT}
          >
            {stringName(tuning, string)}
          </text>
        </g>
      ))}
      {layout.barLines.map((x) => (
        <line
          key={x}
          x1={x}
          x2={x}
          y1={stringY(1)}
          y2={stringY(6)}
          stroke="var(--line)"
          strokeWidth={1.2}
        />
      ))}
    </>
  )
}

function ColumnView({
  layout,
  positioned,
  active,
}: {
  layout: SystemLayout
  positioned: PositionedColumn
  active: boolean
}) {
  const { column, cx } = positioned
  return (
    <g data-role="column">
      {column.annotations.map((annotation) => (
        <text
          key={annotation.text}
          data-role="technique"
          x={annotationX(layout, positioned, annotation)}
          y={ANNOTATION_Y}
          textAnchor="middle"
          fontSize={annotation.text === 'PM' ? 9 : 11}
          fontWeight={annotation.text === 'PM' ? 400 : 600}
          fill={annotation.text === 'PM' ? 'var(--muted)' : 'var(--accent)'}
          style={FONT}
        >
          {annotation.text}
        </text>
      ))}
      {column.notes.map((note) => {
        const y = stringY(note.string)
        const boxWidth = note.label.length > 1 ? 22 : 15
        return (
          <g key={note.index} data-role="note" data-active={active}>
            <rect
              x={cx - boxWidth / 2}
              y={y - NOTE_BOX_HEIGHT / 2}
              width={boxWidth}
              height={NOTE_BOX_HEIGHT}
              rx={4}
              fill={active ? 'var(--accent)' : 'var(--bg)'}
            />
            <text
              data-role="fret"
              x={cx}
              y={y + 4.3}
              textAnchor="middle"
              fontSize={12.5}
              fontWeight={600}
              fill={active ? 'var(--accent-ink)' : 'var(--text)'}
              style={FONT}
            >
              {note.label}
            </text>
          </g>
        )
      })}
    </g>
  )
}

export function Tab({
  notation,
  activeIndex = null,
  activeIndices,
  width,
}: TabProps) {
  const indices = activeIndices ?? (activeIndex === null ? [] : [activeIndex])
  const [ref, measured] = useContainerWidth<HTMLDivElement>(width)
  const totalWidth = measured > 0 ? measured : FALLBACK_WIDTH
  const tuning = notation.tuning ?? STANDARD_TUNING

  const columns = buildColumns(
    notation.events ?? [],
    beatsPerBar(notation.time_signature),
  )
  const systems = partitionSystems(columns, totalWidth - SYSTEM_CHROME).map(
    layoutSystem,
  )

  return (
    <div
      ref={ref}
      role="img"
      aria-label={buildLabel(notation)}
      style={{
        width: width ?? '100%',
        overflowX: 'auto',
        background: 'var(--bg)',
        boxShadow: 'inset 0 0 0 1px var(--line)',
        borderRadius: 12,
        padding: '10px 0',
        boxSizing: 'border-box',
      }}
    >
      {systems.map((layout, i) => (
        <svg
          key={i}
          aria-hidden="true"
          width={totalWidth}
          height={SYSTEM_HEIGHT}
          viewBox={`0 0 ${totalWidth} ${SYSTEM_HEIGHT}`}
          style={{ display: 'block' }}
        >
          <StringsAndNames layout={layout} tuning={tuning} />
          {layout.columns.map((positioned) => (
            <ColumnView
              key={positioned.column.t}
              layout={layout}
              positioned={positioned}
              active={positioned.column.notes.some((n) =>
                indices.includes(n.index),
              )}
            />
          ))}
        </svg>
      ))}
    </div>
  )
}
