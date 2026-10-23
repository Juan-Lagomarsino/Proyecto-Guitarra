import { noteAt, sameNote, STANDARD_TUNING } from '../../notation/pitch'
import type { ChartChord } from '../../songs/types'
import './ChordDiagram.css'

type ChordShape = Pick<ChartChord, 'name' | 'shape' | 'barre'>
type Fret = number | 'x'

export interface ChordDiagramProps {
  chord: ChordShape
  /** Dedo por cuerda, de la 6ta a la 1ra (null/undefined = sin dedo). */
  fingers?: (number | null | undefined)[]
  /** Nota tónica (ej. "C"): se resaltan los puntos que suenan esa nota. */
  tonic?: string
  /** Ancho en px del SVG; el alto se deduce de la proporción. */
  size?: number
}

const STRING_COUNT = 6
const WIDTH = 132
const LEFT = 26
const STRING_GAP = 16
const TOP = 46
const ROW = 20
const DOT_RADIUS = 7
const NUT_FRETS_LIMIT = 4
const MIN_ROWS = 4
const MAX_ROWS = 5

interface Window {
  start: number
  rows: number
  hasNut: boolean
}

const isFretted = (fret: Fret): fret is number => fret !== 'x' && fret > 0

/** Traste de cada cuerda pisada, incluida la cejilla. */
function frettedFrets({ shape, barre }: ChordShape): number[] {
  const frets = shape.filter(isFretted)
  return barre ? [...frets, barre.fret] : frets
}

export function computeWindow(chord: ChordShape): Window {
  const frets = frettedFrets(chord)
  if (frets.length === 0 || Math.max(...frets) <= NUT_FRETS_LIMIT) {
    return { start: 1, rows: MIN_ROWS, hasNut: true }
  }
  const start = Math.min(...frets)
  return { start, rows: MAX_ROWS, hasNut: start === 1 }
}

const stringX = (index: number) => LEFT + index * STRING_GAP
const rowCenter = (fret: number, start: number) =>
  TOP + (fret - start) * ROW + ROW / 2
const height = (rows: number) => TOP + rows * ROW + 12

/** `index` 0 = cuerda 6; la cuerda 6 va a la izquierda. */
const stringNumber = (index: number) => STRING_COUNT - index

function describeString(fret: Fret, index: number): string {
  const label = `cuerda ${stringNumber(index)}`
  if (fret === 'x') return `${label} muteada`
  return fret === 0 ? `${label} al aire` : `${label} traste ${fret}`
}

function ariaLabel(chord: ChordShape, tonic?: string): string {
  const parts = chord.shape.map(describeString)
  if (chord.barre) {
    const { fret, from_string, to_string } = chord.barre
    parts.unshift(
      `cejilla en el traste ${fret}, cuerdas ${from_string} a ${to_string}`,
    )
  }
  const tonicText = tonic ? `. Tónica ${tonic}` : ''
  return `Acorde ${chord.name}: ${parts.join(', ')}${tonicText}`
}

function Grid({ window }: { window: Window }) {
  const bottom = TOP + window.rows * ROW
  const right = stringX(STRING_COUNT - 1)
  return (
    <>
      {Array.from({ length: window.rows + 1 }, (_, i) => (
        <line
          key={i}
          className={
            i === 0 && window.hasNut
              ? 'chord-diagram__nut'
              : 'chord-diagram__fret'
          }
          data-testid={i === 0 && window.hasNut ? 'nut' : undefined}
          x1={LEFT}
          x2={right}
          y1={TOP + i * ROW}
          y2={TOP + i * ROW}
        />
      ))}
      {Array.from({ length: STRING_COUNT }, (_, i) => (
        <line
          key={i}
          className="chord-diagram__string"
          data-testid="string"
          x1={stringX(i)}
          x2={stringX(i)}
          y1={TOP}
          y2={bottom}
        />
      ))}
    </>
  )
}

function StringMarker({
  fret,
  index,
  tonic,
}: {
  fret: Fret
  index: number
  tonic?: string
}) {
  const text = fret === 'x' ? 'x' : fret === 0 ? 'o' : ''
  return (
    <text
      className={`chord-diagram__marker${fret === 0 && isTonic(index, 0, tonic) ? ' chord-diagram__marker--tonic' : ''}`}
      data-testid="string-marker"
      x={stringX(index)}
      y={TOP - 10}
      textAnchor="middle"
    >
      {text}
    </text>
  )
}

function Barre({ chord, window }: { chord: ChordShape; window: Window }) {
  if (!chord.barre) return null
  const { fret, from_string, to_string } = chord.barre
  const fromX = stringX(STRING_COUNT - from_string)
  const toX = stringX(STRING_COUNT - to_string)
  const cy = rowCenter(fret, window.start)
  return (
    <rect
      className="chord-diagram__barre"
      data-testid="barre"
      data-from-x={fromX}
      data-to-x={toX}
      x={fromX - DOT_RADIUS}
      y={cy - DOT_RADIUS}
      width={toX - fromX + DOT_RADIUS * 2}
      height={DOT_RADIUS * 2}
      rx={DOT_RADIUS}
    />
  )
}

function isCoveredByBarre(chord: ChordShape, index: number, fret: number) {
  const { barre } = chord
  if (!barre || barre.fret !== fret) return false
  const string = stringNumber(index)
  return string <= barre.from_string && string >= barre.to_string
}

function isTonic(index: number, fret: number, tonic?: string): boolean {
  if (!tonic) return false
  return sameNote(noteAt(STANDARD_TUNING, stringNumber(index), fret), tonic)
}

function Dots({
  chord,
  window,
  fingers,
  tonic,
}: {
  chord: ChordShape
  window: Window
  fingers?: ChordDiagramProps['fingers']
  tonic?: string
}) {
  return (
    <>
      {chord.shape.map((fret, index) => {
        if (!isFretted(fret)) return null
        const tonicDot = isTonic(index, fret, tonic)
        // Bajo la cejilla solo se dibuja el punto de la tónica.
        if (isCoveredByBarre(chord, index, fret) && !tonicDot) return null
        const finger = fingers?.[index]
        return (
          <g key={index}>
            <circle
              className={`chord-diagram__dot chord-diagram__dot--${tonicDot ? 'tonic' : 'other'}`}
              data-testid="dot"
              data-string={stringNumber(index)}
              data-fret={fret}
              data-tonic={tonicDot}
              cx={stringX(index)}
              cy={rowCenter(fret, window.start)}
              r={DOT_RADIUS}
            />
            {finger ? (
              <text
                className={`chord-diagram__finger chord-diagram__finger--${tonicDot ? 'tonic' : 'other'}`}
                data-testid="finger"
                x={stringX(index)}
                y={rowCenter(fret, window.start) + 3.5}
                textAnchor="middle"
              >
                {finger}
              </text>
            ) : null}
          </g>
        )
      })}
    </>
  )
}

export function ChordDiagram({
  chord,
  fingers,
  tonic,
  size = WIDTH,
}: ChordDiagramProps) {
  const window = computeWindow(chord)
  const viewHeight = height(window.rows)
  return (
    <svg
      className="chord-diagram"
      viewBox={`0 0 ${WIDTH} ${viewHeight}`}
      width={size}
      height={(size * viewHeight) / WIDTH}
      role="img"
      aria-label={ariaLabel(chord, tonic)}
    >
      <text
        className="chord-diagram__name"
        x={WIDTH / 2}
        y={18}
        textAnchor="middle"
      >
        {chord.name}
      </text>
      {chord.shape.map((fret, index) => (
        <StringMarker key={index} fret={fret} index={index} tonic={tonic} />
      ))}
      <Grid window={window} />
      {!window.hasNut && (
        <text
          className="chord-diagram__start"
          data-testid="start-fret"
          x={stringX(STRING_COUNT - 1) + 10}
          y={rowCenter(window.start, window.start) + 4}
        >
          {window.start}fr
        </text>
      )}
      <Barre chord={chord} window={window} />
      <Dots chord={chord} window={window} fingers={fingers} tonic={tonic} />
    </svg>
  )
}
