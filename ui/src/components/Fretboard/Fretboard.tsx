import { noteAt, sameNote, STANDARD_TUNING } from '../../notation/pitch'
import type { Notation } from '../../notation/types'
import './Fretboard.css'
import {
  boardHeight,
  boardWidth,
  collectPositions,
  computeFretRange,
  fretLineX,
  fretX,
  LEFT,
  RIGHT_PAD,
  STRING_COUNT,
  stringsBottom,
  stringY,
  TOP,
  type FretRange,
  type Position,
} from './layout'

type NoteState = 'tonic' | 'active' | 'other'

const STRING_NAMES = ['e', 'B', 'G', 'D', 'A', 'E'] // índice 0 = cuerda 1
// Incrustaciones: la referencia (drawBoard) también marca el 15, así que se mantiene.
// Quedan fuera `win` (ventana resaltada) y las etiquetas dentro de las notas: el JSON
// oficial no trae dedo ni grado, y el contrato de props de T16 no incluye `win`.
const INLAY_FRETS = [3, 5, 7, 9, 15]
const DOUBLE_INLAY_FRET = 12
const NOTE_RADIUS = 10.5
const ACTIVE_NOTE_RADIUS = 12.5

export interface FretboardProps {
  notation: Notation
  /** Índice en `notation.events` del evento que suena ahora. */
  activeIndex?: number | null
  /** Índices que suenan a la vez (un acorde); si viene, manda sobre `activeIndex`. */
  activeIndices?: readonly number[]
  /** Trastes visibles [desde, hasta]. Si falta, se calcula de los eventos. */
  fretRange?: [number, number]
  showLegend?: boolean
}

const frets = ([lo, hi]: FretRange) =>
  Array.from({ length: hi - lo + 1 }, (_, i) => lo + i)

function boardLabel(range: FretRange, tonic: string | null | undefined) {
  const [lo, hi] = range
  const base = `Mástil de la guitarra, trastes ${lo} a ${hi}`
  return tonic ? `${base}. Tónica: ${tonic}` : base
}

function noteState(
  position: Position,
  active: readonly Position[],
  tonicMatches: boolean,
): NoteState {
  if (
    active.some((a) => a.string === position.string && a.fret === position.fret)
  ) {
    return 'active'
  }
  return tonicMatches ? 'tonic' : 'other'
}

function FretColumns({ range }: { range: FretRange }) {
  const [lo] = range
  const bottom = stringsBottom()
  return (
    <>
      {lo > 0 && (
        <line
          className="fretboard__fret"
          x1={LEFT}
          x2={LEFT}
          y1={TOP}
          y2={bottom}
        />
      )}
      {frets(range).map((fret) => (
        <g key={fret}>
          <line
            className={fret === 0 ? 'fretboard__nut' : 'fretboard__fret'}
            x1={fretLineX(fret, range)}
            x2={fretLineX(fret, range)}
            y1={TOP}
            y2={bottom}
          />
          <text
            className="fretboard__label"
            data-testid="fret-number"
            x={fretX(fret, range)}
            y={bottom + 20}
            textAnchor="middle"
          >
            {fret}
          </text>
        </g>
      ))}
    </>
  )
}

function Inlays({ range }: { range: FretRange }) {
  const cy = stringsBottom() + 30
  const dot = (fret: number, dx: number) => (
    <circle
      key={`${fret}${dx}`}
      className="fretboard__inlay"
      data-inlay={fret}
      cx={fretX(fret, range) + dx}
      cy={cy}
      r={2.5}
    />
  )
  return (
    <>
      {frets(range).flatMap((fret) => {
        if (INLAY_FRETS.includes(fret)) return [dot(fret, 0)]
        if (fret === DOUBLE_INLAY_FRET) return [dot(fret, -6), dot(fret, 6)]
        return []
      })}
    </>
  )
}

function Strings({ range }: { range: FretRange }) {
  const right = boardWidth(range) - RIGHT_PAD
  return (
    <>
      {Array.from({ length: STRING_COUNT }, (_, i) => i + 1).map((string) => (
        <g key={string}>
          <line
            className="fretboard__string"
            x1={LEFT}
            x2={right}
            y1={stringY(string)}
            y2={stringY(string)}
            strokeWidth={1 + (string - 1) * 0.25}
          />
          <text
            className="fretboard__label"
            data-testid="string-name"
            x={LEFT - 12}
            y={stringY(string) + 4}
            textAnchor="middle"
          >
            {STRING_NAMES[string - 1]}
          </text>
        </g>
      ))}
    </>
  )
}

function Legend() {
  const items: [NoteState, string][] = [
    ['tonic', 'Tónica'],
    ['other', 'Otras notas'],
    ['active', 'Suena ahora'],
  ]
  return (
    <div className="fretboard__legend">
      {items.map(([state, text]) => (
        <span key={state}>
          <i className={`fretboard__swatch fretboard__swatch--${state}`} />
          {text}
        </span>
      ))}
    </div>
  )
}

export function Fretboard({
  notation,
  activeIndex = null,
  activeIndices,
  fretRange,
  showLegend = true,
}: FretboardProps) {
  const events = notation.events ?? []
  const tuning = notation.tuning ?? STANDARD_TUNING
  const range = fretRange ?? computeFretRange(events)
  const indices = activeIndices ?? (activeIndex === null ? [] : [activeIndex])
  const active = indices.flatMap((index) => {
    const event = events[index]
    return event ? [{ string: event.string, fret: event.fret }] : []
  })

  return (
    <div className="fretboard">
      <div className="fretboard__board">
        <svg
          className="fretboard__svg"
          viewBox={`0 0 ${boardWidth(range)} ${boardHeight()}`}
          role="img"
          aria-label={boardLabel(range, notation.tonic)}
        >
          <FretColumns range={range} />
          <Inlays range={range} />
          <Strings range={range} />
          {collectPositions(events).map((position) => {
            const tonicMatches =
              !!notation.tonic &&
              sameNote(
                noteAt(tuning, position.string, position.fret),
                notation.tonic,
              )
            const state = noteState(position, active, tonicMatches)
            return (
              <circle
                key={`${position.string}-${position.fret}`}
                className={`fretboard__note--${state}`}
                data-testid="note"
                data-state={state}
                data-string={position.string}
                data-fret={position.fret}
                cx={fretX(position.fret, range)}
                cy={stringY(position.string)}
                r={state === 'active' ? ACTIVE_NOTE_RADIUS : NOTE_RADIUS}
              />
            )
          })}
        </svg>
      </div>
      {showLegend && <Legend />}
    </div>
  )
}
