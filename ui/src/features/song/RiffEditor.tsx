import { useState } from 'react'
import { ApiError } from '../../api/client'
import { saveUserChart, type SongChartResponse } from '../../api/songs'
import { Tab } from '../../components/Tab/Tab'
import { isLowConfidenceEvent } from '../../notation/confidence'
import type { NoteEvent } from '../../notation/types'
import type { ChartSection, SongChartContent } from '../../songs/types'
import { replaceSection } from './chartEdit'
import { LOW_CONFIDENCE } from './chartView'
import {
  addNote,
  buildRiff,
  canUndo,
  changeBend,
  changeDuration,
  changeFret,
  changeStringFree,
  changeStringKeepingPitch,
  changeTechnique,
  deleteSelected,
  DURATIONS,
  MAX_BEND,
  MAX_FRET,
  riffProblem,
  sectionLengthBeats,
  selectNote,
  startDraft,
  TECHNIQUES,
  undo,
  type RiffDraft,
  type Technique,
} from './riffEdit'
import './chartEdit.css'
import './riffEditor.css'

interface RiffEditorProps {
  songId: number
  content: SongChartContent
  section: ChartSection
  onSaved: (chart: SongChartResponse) => void
  onCancel: () => void
}

const STRINGS = [1, 2, 3, 4, 5, 6]
const FRETS = Array.from({ length: MAX_FRET + 1 }, (_, fret) => fret)
const BENDS = [0.5, 1, 1.5, 2, 3, 4].filter((b) => b <= MAX_BEND)

const TECHNIQUE_NAMES: Record<Technique, string> = {
  h: 'h · hammer-on',
  p: 'p · pull-off',
  '/': '/ · slide ascendente',
  '\\': '\\ · slide descendente',
  b: 'b · bend',
  r: 'r · release',
  '~': '~ · vibrato',
  pm: 'pm · palm mute',
  x: 'x · muteada',
}

const DURATION_NAMES: Record<number, string> = {
  0.25: '1/4 de beat',
  0.5: '1/2 beat',
  1: '1 beat',
  2: '2 beats',
}

const durationName = (dur: number) =>
  Math.abs(dur - 1 / 3) < 1e-6
    ? '1/3 de beat'
    : (DURATION_NAMES[dur] ?? `${dur} beats`)

const formatBeat = (t: number) => String(Math.round(t * 1000) / 1000)

const noteLabel = (event: NoteEvent) =>
  `Tiempo ${formatBeat(event.t)}, cuerda ${event.string}, traste ${event.fret}` +
  (event.technique ? `, técnica ${event.technique}` : '')

/** Mensaje legible de un error del PUT; los 422 traen el detalle de la validación. */
export function saveErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    const detail = error.detail
    if (Array.isArray(detail)) {
      const reasons = detail
        .map((item) => (item as { msg?: unknown }).msg)
        .filter((msg): msg is string => typeof msg === 'string')
      if (reasons.length > 0)
        return `La API no aceptó el riff: ${reasons.join('; ')}`
    }
    return `La API no aceptó el riff: ${error.message}`
  }
  return error instanceof Error ? error.message : 'Error desconocido'
}

function NoteList({
  draft,
  onSelect,
}: {
  draft: RiffDraft
  onSelect: (index: number) => void
}) {
  if (draft.events.length === 0)
    return <p className="page-note">Todavía no hay notas. Agregá la primera.</p>
  return (
    <ul className="riff-edit__notes" aria-label="Notas del riff">
      {draft.events.map((event, index) => (
        <li key={`${index}-${event.t}-${event.string}`}>
          <button
            type="button"
            className="riff-edit__note"
            aria-pressed={index === draft.selected}
            aria-label={noteLabel(event)}
            data-confidence={
              isLowConfidenceEvent(event, LOW_CONFIDENCE) ? 'low' : 'ok'
            }
            onClick={() => onSelect(index)}
          >
            <span className="riff-edit__note-time">{formatBeat(event.t)}</span>
            <span>
              {event.string}/{event.fret}
            </span>
            {event.technique && <span>{event.technique}</span>}
          </button>
        </li>
      ))}
    </ul>
  )
}

function Select<T extends string | number>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <label className="chart-edit__field">
      <span>{label}</span>
      <select
        value={String(value)}
        onChange={(e) => {
          const picked = options.find((o) => String(o.value) === e.target.value)
          if (picked) onChange(picked.value)
        }}
      >
        {options.map((option) => (
          <option key={String(option.value)} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

const fretOptions = FRETS.map((fret) => ({ value: fret, label: String(fret) }))
const stringOptions = STRINGS.map((s) => ({ value: s, label: `Cuerda ${s}` }))

function NoteControls({
  draft,
  event,
  update,
}: {
  draft: RiffDraft
  event: NoteEvent
  update: (change: (draft: RiffDraft) => RiffDraft) => void
}) {
  const [freeString, setFreeString] = useState(false)
  const techniqueOptions = [
    { value: '', label: 'Ninguna' },
    ...TECHNIQUES.map((t) => ({
      value: t as string,
      label: TECHNIQUE_NAMES[t],
    })),
  ]
  return (
    <fieldset className="riff-edit__controls">
      <legend>Nota elegida</legend>
      <div className="riff-edit__grid">
        <Select
          label="Traste"
          value={event.fret}
          options={fretOptions}
          onChange={(fret) => update((d) => changeFret(d, fret))}
        />
        <Select
          label="Cuerda"
          value={event.string}
          options={stringOptions}
          onChange={(string) =>
            update((d) =>
              freeString
                ? changeStringFree(d, string)
                : changeStringKeepingPitch(d, string),
            )
          }
        />
        <Select
          label="Duración"
          value={DURATIONS.find((d) => Math.abs(d - event.dur) < 1e-6) ?? 1}
          options={DURATIONS.map((d) => ({
            value: d,
            label: durationName(d),
          }))}
          onChange={(dur) => update((d) => changeDuration(d, dur))}
        />
        <Select
          label="Técnica"
          value={event.technique ?? ''}
          options={techniqueOptions}
          onChange={(t) =>
            update((d) =>
              changeTechnique(d, t === '' ? null : (t as Technique)),
            )
          }
        />
        {event.technique === 'b' && (
          <Select
            label="Bend (semitonos)"
            value={event.bend ?? 1}
            options={BENDS.map((b) => ({ value: b, label: String(b) }))}
            onChange={(bend) => update((d) => changeBend(d, bend))}
          />
        )}
      </div>
      <label className="riff-edit__check">
        <input
          type="checkbox"
          checked={freeString}
          onChange={(e) => setFreeString(e.target.checked)}
        />
        <span>Cuerda con traste libre (no mantener la altura)</span>
      </label>
      <button
        type="button"
        className="chart-edit__button"
        onClick={() => update(deleteSelected)}
        disabled={draft.selected === null}
      >
        Borrar nota
      </button>
    </fieldset>
  )
}

function AddNoteForm({
  onAdd,
}: {
  onAdd: (note: { t: number; string: number; fret: number }) => void
}) {
  const [t, setT] = useState('0')
  const [string, setString] = useState(1)
  const [fret, setFret] = useState(0)
  return (
    <fieldset className="riff-edit__controls">
      <legend>Agregar nota</legend>
      <div className="riff-edit__grid">
        <label className="chart-edit__field">
          <span>Tiempo (beats desde el inicio)</span>
          <input
            type="number"
            inputMode="decimal"
            step="0.25"
            min="0"
            value={t}
            onChange={(e) => setT(e.target.value)}
          />
        </label>
        <Select
          label="Cuerda nueva"
          value={string}
          options={stringOptions}
          onChange={setString}
        />
        <Select
          label="Traste nuevo"
          value={fret}
          options={fretOptions}
          onChange={setFret}
        />
      </div>
      <button
        type="button"
        className="chart-edit__button"
        onClick={() => onAdd({ t: t === '' ? NaN : Number(t), string, fret })}
      >
        Agregar nota
      </button>
    </fieldset>
  )
}

/**
 * Editor del riff de una sección. Se elige una lista de notas y no la tab SVG: a 375 px las
 * columnas de la tab quedan de pocos píxeles, y una lista de botones es accesible y de 40 px
 * de alto. La tab se muestra igual, como vista previa del borrador.
 */
export function RiffEditor({
  songId,
  content,
  section,
  onSaved,
  onCancel,
}: RiffEditorProps) {
  const base = section.riff ?? null
  const [draft, setDraft] = useState(() =>
    startDraft(base?.events ?? [], base?.tuning),
  )
  const [failure, setFailure] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const update = (change: (draft: RiffDraft) => RiffDraft) => setDraft(change)
  const selectedEvent =
    draft.selected === null ? null : draft.events[draft.selected]
  const problem = riffProblem(
    draft.events,
    sectionLengthBeats(content, section),
  )
  const preview = buildRiff(base, content.bpm, draft.events)

  async function save() {
    if (problem) return
    setSaving(true)
    setFailure(null)
    try {
      const edited = replaceSection(content, section.id, { riff: preview })
      onSaved(await saveUserChart(songId, content.instrument, edited))
    } catch (error) {
      setFailure(saveErrorMessage(error))
      setSaving(false)
    }
  }

  return (
    <section
      className="riff-edit chart-edit__form"
      aria-label={`Editar riff de ${section.name}`}
    >
      <h4 className="song-subtitle">Editar riff</h4>
      {draft.events.length > 0 && (
        <div className="song-riff__tab">
          <Tab
            notation={preview}
            activeIndices={draft.selected === null ? [] : [draft.selected]}
            lowConfidenceBelow={LOW_CONFIDENCE}
          />
        </div>
      )}
      <NoteList
        draft={draft}
        onSelect={(i) => update((d) => selectNote(d, i))}
      />
      {selectedEvent && (
        <NoteControls draft={draft} event={selectedEvent} update={update} />
      )}
      <AddNoteForm onAdd={(note) => update((d) => addNote(d, note))} />

      {draft.warning && (
        <p role="status" className="chart-edit__problem">
          {draft.warning}
        </p>
      )}
      {problem && draft.events.length > 0 && (
        <p role="alert" className="chart-edit__problem">
          {problem}
        </p>
      )}
      {failure && (
        <p role="alert" className="chart-edit__problem">
          {failure}
        </p>
      )}
      <div className="chart-edit__actions">
        <button
          type="button"
          className="chart-edit__save"
          onClick={() => void save()}
          disabled={saving || problem !== null}
        >
          {saving ? 'Guardando…' : 'Guardar'}
        </button>
        <button
          type="button"
          className="chart-edit__button"
          onClick={() => update(undo)}
          disabled={saving || !canUndo(draft)}
        >
          Deshacer
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
    </section>
  )
}
