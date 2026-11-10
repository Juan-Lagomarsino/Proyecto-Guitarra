import { useCallback, useState } from 'react'
import {
  fetchChordShapePreferences,
  fetchChordShapes,
  type ChordShapeOption,
} from '../../api/songs'
import { ChordDiagram } from '../../components/ChordDiagram/ChordDiagram'
import { useAsyncData } from '../study/useAsyncData'
import { preferredShape } from './chartEdit'
import './chartEdit.css'

interface ChordShapePickerProps {
  /** Número del acorde en la sección (desde 1), para las etiquetas. */
  position: number
  /** Nombre del acorde tal como suena en la canción. */
  name: string
  instrument: string
  capo: number
  /** Forma que tiene ahora el acorde en el chart editado. */
  current: Pick<ChordShapeOption, 'shape'>
  onSelect: (option: ChordShapeOption) => void
}

const sameShape = (
  a: ChordShapeOption['shape'],
  b: ChordShapeOption['shape'],
) => a.length === b.length && a.every((fret, i) => fret === b[i])

async function loadOptions(name: string, capo: number, signal: AbortSignal) {
  const shapes = await fetchChordShapes(name, capo, signal)
  // Lo aprendido es un extra: si falla, se muestran las formas igual.
  const preferences = await fetchChordShapePreferences(signal).catch(() => ({}))
  return { shapes, preferences }
}

function ShapeOptions({
  position,
  name,
  instrument,
  capo,
  current,
  onSelect,
}: ChordShapePickerProps) {
  const load = useCallback(
    (signal: AbortSignal) => loadOptions(name, capo, signal),
    [name, capo],
  )
  const state = useAsyncData(load)
  if (state.status === 'loading')
    return <p className="chart-edit__hint">Cargando formas…</p>
  if (state.status === 'error')
    return (
      <p role="alert" className="chart-edit__problem">
        No pude traer las formas de {name}.
      </p>
    )
  const { shapes, preferences } = state.data
  const preferred = preferredShape(preferences, instrument, name, capo, shapes)
  return (
    <div
      className="chart-edit__shapes"
      role="group"
      aria-label={`Formas del acorde ${position}`}
    >
      {shapes.map((option) => {
        const isPreferred = option === preferred
        return (
          <button
            key={option.shape.join(',')}
            type="button"
            className="chart-edit__shape"
            aria-pressed={sameShape(option.shape, current.shape)}
            aria-label={`Forma ${option.shape.join(' ')}${isPreferred ? ' (preferida)' : ''}`}
            onClick={() => onSelect(option)}
          >
            <ChordDiagram chord={option} size={72} />
            {isPreferred && (
              <span className="chart-edit__preferred">Preferida</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Alternativas de forma de un acorde como mini diagramas; se cargan al abrir. */
export function ChordShapePicker(props: ChordShapePickerProps) {
  const [open, setOpen] = useState(false)
  return (
    <div className="chart-edit__picker">
      <button
        type="button"
        className="chart-edit__button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        Elegir forma del acorde {props.position}
      </button>
      {open && <ShapeOptions {...props} />}
    </div>
  )
}
