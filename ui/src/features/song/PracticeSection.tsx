import { useState } from 'react'
import {
  createSectionExercise,
  type ChartInstrument,
  type SectionExerciseType,
} from '../../api/songs'
import './practice.css'

const TYPES: { value: SectionExerciseType; label: string }[] = [
  { value: 'chords', label: 'Cambio de acordes' },
  { value: 'strumming', label: 'Rasgueo' },
]
const RIFF_TYPE = { value: 'riff', label: 'Riff' } as const

interface Props {
  songId: number
  /** Id en la base de la sección elegida (no el slug del chart). */
  sectionId: number
  sectionName: string
  instrument: ChartInstrument
  /** La sección tiene riff: se ofrece también ese tipo de ejercicio. */
  hasRiff?: boolean
  onCreated: () => void
}

/** Botón "Practicar esta sección": elige el tipo y crea el ejercicio en la API. */
export function PracticeSection({
  songId,
  sectionId,
  sectionName,
  instrument,
  hasRiff = false,
  onCreated,
}: Props) {
  const types = hasRiff ? [...TYPES, RIFF_TYPE] : TYPES
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<SectionExerciseType>('chords')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState(false)

  async function create() {
    setSaving(true)
    setError(null)
    try {
      await createSectionExercise(songId, sectionId, type, instrument)
      setCreated(true)
      setOpen(false)
      onCreated()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Error desconocido')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="practice">
      {!open && (
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => {
            setOpen(true)
            setCreated(false)
          }}
        >
          Practicar esta sección
        </button>
      )}
      {open && (
        <fieldset className="practice__form">
          <legend>¿Qué querés practicar de {sectionName}?</legend>
          <div className="practice__types" role="group">
            {types.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                className="btn"
                aria-pressed={value === type}
                onClick={() => setType(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="practice__actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={create}
              disabled={saving}
            >
              Crear ejercicio
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => setOpen(false)}
              disabled={saving}
            >
              Cancelar
            </button>
          </div>
        </fieldset>
      )}
      {created && (
        <p className="study-status" role="status">
          Listo, el ejercicio quedó en &ldquo;Tus ejercicios&rdquo;.
        </p>
      )}
      {error && (
        <p className="study-status study-status--error" role="alert">
          No se pudo crear el ejercicio: {error}
        </p>
      )}
    </div>
  )
}
