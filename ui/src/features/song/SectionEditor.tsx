import { useCallback, useState, type FormEvent } from 'react'
import {
  fetchChordShapes,
  type ChordShapeOption,
  fetchStrumPatterns,
  saveUserChart,
  type SongChartResponse,
  type StrumPatternEntry,
} from '../../api/songs'
import type {
  ChartChord,
  ChartSection,
  SongChartContent,
} from '../../songs/types'
import { useAsyncData } from '../study/useAsyncData'
import { ChordShapePicker } from './ChordShapePicker'
import {
  patternOptions,
  replaceSection,
  sectionProblem,
  withPattern,
} from './chartEdit'
import './chartEdit.css'

interface SectionEditorProps {
  songId: number
  content: SongChartContent
  section: ChartSection
  onSaved: (chart: SongChartResponse) => void
  onCancel: () => void
}

const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : 'Error desconocido'

/** Resuelve la forma del acorde nuevo desde el diccionario de la API. */
async function chordFromName(
  previous: ChartChord,
  name: string,
  capo: number,
): Promise<ChartChord> {
  let shapes: ChordShapeOption[]
  try {
    shapes = await fetchChordShapes(name, capo)
  } catch {
    shapes = []
  }
  const best = shapes[0]
  if (!best) throw new Error(`No encontré el acorde "${name}".`)
  return {
    t_s: previous.t_s,
    name: best.name,
    shape: best.shape,
    barre: best.barre,
    confidence: 1,
  }
}

/** Con otro nombre se recalcula la forma; con el mismo, se respeta la forma elegida (si hay). */
async function editedChords(
  chords: ChartChord[],
  names: string[],
  picked: Record<number, ChordShapeOption>,
  capo: number,
): Promise<ChartChord[]> {
  return Promise.all(
    chords.map((chord, index) => {
      const name = (names[index] ?? chord.name).trim()
      if (name !== chord.name) return chordFromName(chord, name, capo)
      const choice = picked[index]
      return choice
        ? { ...chord, shape: choice.shape, barre: choice.barre }
        : chord
    }),
  )
}

function PatternSelect({
  options,
  value,
  label,
  onChange,
}: {
  options: StrumPatternEntry[]
  value: string
  label: string
  onChange: (id: string) => void
}) {
  return (
    <label className="chart-edit__field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Dejar como está</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name} ({option.pattern})
          </option>
        ))}
      </select>
    </label>
  )
}

export function SectionEditor({
  songId,
  content,
  section,
  onSaved,
  onCancel,
}: SectionEditorProps) {
  const chords = section.chords ?? []
  const [name, setName] = useState(section.name)
  const [start, setStart] = useState(String(section.start_s))
  const [end, setEnd] = useState(String(section.end_s))
  const [chordNames, setChordNames] = useState(chords.map((c) => c.name))
  const [picked, setPicked] = useState<Record<number, ChordShapeOption>>({})
  const [patternId, setPatternId] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const loadPatterns = useCallback(
    (signal: AbortSignal) => fetchStrumPatterns(signal),
    [],
  )
  const catalog = useAsyncData(loadPatterns)
  const kind =
    content.instrument === 'classical' && section.arpeggio
      ? 'arpeggio'
      : 'strum'
  const currentId = (kind === 'arpeggio' ? section.arpeggio : section.strum)
    ?.pattern_id
  const options =
    catalog.status === 'ready'
      ? patternOptions(
          catalog.data,
          kind,
          content.time_signature,
          currentId ?? null,
        )
      : []

  async function submit(event: FormEvent) {
    event.preventDefault()
    const bounds = {
      name: name.trim(),
      start_s: Number(start),
      end_s: Number(end),
    }
    const invalid = sectionProblem(content, section.id, bounds)
    if (invalid) return setProblem(invalid)
    setSaving(true)
    setProblem(null)
    try {
      const next = await editedChords(
        chords,
        chordNames,
        picked,
        content.capo ?? 0,
      )
      const changedChords = next.some((chord, i) => chord !== chords[i])
      const chosen = options.find((option) => option.id === patternId)
      const edited = replaceSection(content, section.id, {
        ...bounds,
        ...(changedChords && { chords: next, chord_source: 'user' as const }),
        ...(chosen && withPattern(chosen)),
      })
      onSaved(await saveUserChart(songId, content.instrument, edited))
    } catch (error) {
      setProblem(messageOf(error))
      setSaving(false)
    }
  }

  return (
    <form
      className="chart-edit__form"
      aria-label={`Editar sección ${section.name}`}
      onSubmit={(e) => void submit(e)}
      noValidate
    >
      <label className="chart-edit__field">
        <span>Nombre</span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <div className="chart-edit__row">
        <label className="chart-edit__field">
          <span>Inicio (s)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            min="0"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label className="chart-edit__field">
          <span>Fin (s)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.1"
            min="0"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>

      {chords.length > 0 && (
        <fieldset className="chart-edit__chords">
          <legend>Acordes</legend>
          {chords.map((chord, index) => (
            <div key={index} className="chart-edit__chord">
              <label className="chart-edit__field">
                <span>Acorde {index + 1}</span>
                <input
                  type="text"
                  value={chordNames[index] ?? ''}
                  onChange={(e) =>
                    setChordNames((names) =>
                      names.map((n, i) => (i === index ? e.target.value : n)),
                    )
                  }
                />
              </label>
              {(chordNames[index] ?? chord.name).trim() === chord.name && (
                <ChordShapePicker
                  position={index + 1}
                  name={chord.name}
                  instrument={content.instrument}
                  capo={content.capo ?? 0}
                  current={picked[index] ?? chord}
                  onSelect={(option) =>
                    setPicked((all) => ({ ...all, [index]: option }))
                  }
                />
              )}
            </div>
          ))}
        </fieldset>
      )}

      {catalog.status === 'ready' && options.length > 0 && (
        <PatternSelect
          options={options}
          value={patternId}
          label={
            kind === 'arpeggio' ? 'Patrón de arpegio' : 'Patrón de rasgueo'
          }
          onChange={setPatternId}
        />
      )}

      {problem && (
        <p role="alert" className="chart-edit__problem">
          {problem}
        </p>
      )}
      <div className="chart-edit__actions">
        <button type="submit" className="chart-edit__save" disabled={saving}>
          {saving ? 'Guardando…' : 'Guardar'}
        </button>
        <button
          type="button"
          className="chart-edit__button"
          onClick={onCancel}
          disabled={saving}
        >
          Cancelar
        </button>
      </div>
    </form>
  )
}
