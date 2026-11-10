import { midiOf, STANDARD_TUNING, type Tuning } from '../../notation/pitch'
import type { Notation, NoteEvent } from '../../notation/types'
import type { ChartSection, SongChartContent } from '../../songs/types'

export const MAX_FRET = 22
export const MAX_BEND = 4
/** Valores de duración de la grilla, en beats: semicorchea, tresillo, corchea, negra, blanca. */
export const DURATIONS = [0.25, 1 / 3, 0.5, 1, 2] as const
export const TECHNIQUES = [
  'h',
  'p',
  '/',
  '\\',
  'b',
  'r',
  '~',
  'pm',
  'x',
] as const

export type Technique = (typeof TECHNIQUES)[number]

/** Tolerancia del validador de la API para el largo del riff (ADR 0018). */
const LENGTH_TOLERANCE = 0.01
const DURATION_EPSILON = 1e-6

interface Snapshot {
  events: NoteEvent[]
  selected: number | null
}

/** Estado de la edición: las notas, cuál está elegida y la pila para deshacer. */
export interface RiffDraft extends Snapshot {
  tuning: Tuning
  history: Snapshot[]
  /** Por qué no se aplicó el último cambio; se limpia con el cambio siguiente. */
  warning: string | null
}

export function startDraft(
  events: readonly NoteEvent[],
  tuning: Tuning = STANDARD_TUNING,
): RiffDraft {
  return {
    events: events.map((event) => ({ ...event })),
    selected: null,
    tuning,
    history: [],
    warning: null,
  }
}

export const canUndo = (draft: RiffDraft) => draft.history.length > 0

const reject = (draft: RiffDraft, warning: string): RiffDraft => ({
  ...draft,
  warning,
})

/** Aplica un cambio guardando el estado anterior para poder deshacerlo. */
function commit(
  draft: RiffDraft,
  events: NoteEvent[],
  selected: number | null = draft.selected,
): RiffDraft {
  return {
    ...draft,
    events,
    selected,
    warning: null,
    history: [
      ...draft.history,
      { events: draft.events, selected: draft.selected },
    ],
  }
}

export function selectNote(draft: RiffDraft, index: number | null): RiffDraft {
  const valid = index !== null && index >= 0 && index < draft.events.length
  return { ...draft, selected: valid ? index : null, warning: null }
}

function without(event: NoteEvent, ...keys: (keyof NoteEvent)[]): NoteEvent {
  const copy = { ...event }
  for (const key of keys) delete copy[key]
  return copy
}

/** Reemplaza la nota elegida por una versión del usuario (sin `confidence`). */
function editSelected(
  draft: RiffDraft,
  change: (event: NoteEvent) => NoteEvent,
): RiffDraft {
  const index = draft.selected
  if (index === null) return draft
  const events = draft.events.map((event, i) => {
    if (i !== index) return event
    return without(change(event), 'confidence')
  })
  return commit(draft, events)
}

const isValidFret = (fret: number) =>
  Number.isInteger(fret) && fret >= 0 && fret <= MAX_FRET

const isValidString = (string: number) =>
  Number.isInteger(string) && string >= 1 && string <= 6

const FRET_MESSAGE = `El traste tiene que ser un entero entre 0 y ${MAX_FRET}.`
const STRING_MESSAGE = 'La cuerda tiene que ser de 1 (aguda) a 6 (grave).'
const TAKEN_MESSAGE = 'Ya hay una nota en esa cuerda en ese mismo tiempo.'

const isTaken = (
  events: readonly NoteEvent[],
  t: number,
  string: number,
  ignoring: number | null = null,
) =>
  events.some(
    (event, i) => i !== ignoring && event.t === t && event.string === string,
  )

export function changeFret(draft: RiffDraft, fret: number): RiffDraft {
  if (draft.selected === null) return draft
  if (!isValidFret(fret)) return reject(draft, FRET_MESSAGE)
  return editSelected(draft, (event) => ({ ...event, fret }))
}

const openMidi = (tuning: Tuning, string: number) => midiOf(tuning[6 - string])

/** Cambia de cuerda manteniendo la altura (recalcula el traste). Si no se puede, avisa. */
export function changeStringKeepingPitch(
  draft: RiffDraft,
  string: number,
): RiffDraft {
  const index = draft.selected
  if (index === null) return draft
  const current = draft.events[index]
  if (string === current.string) return draft
  if (!isValidString(string)) return reject(draft, STRING_MESSAGE)
  const pitch = openMidi(draft.tuning, current.string) + current.fret
  const fret = pitch - openMidi(draft.tuning, string)
  if (!isValidFret(fret)) {
    return reject(
      draft,
      `Esa nota no existe en la cuerda ${string} (daría el traste ${fret}).`,
    )
  }
  if (isTaken(draft.events, current.t, string, index))
    return reject(draft, TAKEN_MESSAGE)
  return editSelected(draft, (event) => ({ ...event, string, fret }))
}

/** Cambia de cuerda dejando el traste: la altura cambia. */
export function changeStringFree(draft: RiffDraft, string: number): RiffDraft {
  const index = draft.selected
  if (index === null) return draft
  if (!isValidString(string)) return reject(draft, STRING_MESSAGE)
  if (string === draft.events[index].string) return draft
  if (isTaken(draft.events, draft.events[index].t, string, index))
    return reject(draft, TAKEN_MESSAGE)
  return editSelected(draft, (event) => ({ ...event, string }))
}

/** Pone o saca la técnica; `b` arranca con un bend de 1 semitono y las demás borran el bend. */
export function changeTechnique(
  draft: RiffDraft,
  technique: Technique | null,
): RiffDraft {
  if (draft.selected === null) return draft
  if (technique !== null && !TECHNIQUES.includes(technique))
    return reject(draft, `Técnica desconocida: ${technique}.`)
  return editSelected(draft, (event) => {
    const rest = without(event, 'technique', 'bend')
    if (technique === null) return rest
    if (technique === 'b') return { ...rest, technique, bend: event.bend ?? 1 }
    return { ...rest, technique }
  })
}

/** Semitonos del bend; solo vale en una nota con la técnica `b`. */
export function changeBend(draft: RiffDraft, semitones: number): RiffDraft {
  const index = draft.selected
  if (index === null) return draft
  if (draft.events[index].technique !== 'b')
    return reject(draft, 'El bend solo se puede usar con la técnica b.')
  if (!(semitones > 0 && semitones <= MAX_BEND))
    return reject(draft, `El bend va de 0,5 a ${MAX_BEND} semitonos.`)
  return editSelected(draft, (event) => ({ ...event, bend: semitones }))
}

export function changeDuration(draft: RiffDraft, dur: number): RiffDraft {
  if (draft.selected === null) return draft
  if (!DURATIONS.some((d) => Math.abs(d - dur) < DURATION_EPSILON))
    return reject(draft, 'Esa duración no está en la grilla.')
  return editSelected(draft, (event) => ({ ...event, dur }))
}

export interface NewNote {
  t: number
  string: number
  fret: number
  dur?: number
}

const byTime = (a: NoteEvent, b: NoteEvent) => a.t - b.t || b.string - a.string

/** Agrega una nota en el beat elegido (relativo a la sección) y la deja elegida. */
export function addNote(
  draft: RiffDraft,
  { t, string, fret, dur = 1 }: NewNote,
): RiffDraft {
  if (!(Number.isFinite(t) && t >= 0))
    return reject(draft, 'El tiempo tiene que ser 0 o más.')
  if (!isValidString(string)) return reject(draft, STRING_MESSAGE)
  if (!isValidFret(fret)) return reject(draft, FRET_MESSAGE)
  if (isTaken(draft.events, t, string)) return reject(draft, TAKEN_MESSAGE)
  const note: NoteEvent = { t, dur, string, fret }
  const events = [...draft.events, note].sort(byTime)
  return commit(draft, events, events.indexOf(note))
}

export function deleteSelected(draft: RiffDraft): RiffDraft {
  const index = draft.selected
  if (index === null) return draft
  return commit(
    draft,
    draft.events.filter((_, i) => i !== index),
    null,
  )
}

export function undo(draft: RiffDraft): RiffDraft {
  const previous = draft.history[draft.history.length - 1]
  if (!previous) return draft
  return {
    ...draft,
    ...previous,
    history: draft.history.slice(0, -1),
    warning: null,
  }
}

/** Beat (fraccionario) de un instante, según la grilla; fuera de ella extrapola con el intervalo del borde. */
function secondsToBeats(beats_s: readonly number[], seconds: number): number {
  const last = beats_s.length - 1
  const lower = Math.max(
    0,
    Math.min(last - 1, beats_s.filter((b) => b <= seconds).length - 1),
  )
  const span = beats_s[lower + 1] - beats_s[lower]
  return lower + (seconds - beats_s[lower]) / span
}

/** Largo de la sección en beats, con la misma cuenta que la API (ADR 0018). */
export function sectionLengthBeats(
  content: SongChartContent,
  section: ChartSection,
): number {
  const grid = content.beat_grid?.beats_s
  if (grid && grid.length >= 2) {
    return (
      secondsToBeats(grid, section.end_s) -
      secondsToBeats(grid, section.start_s)
    )
  }
  return ((section.end_s - section.start_s) * content.bpm) / 60
}

const beatsText = (beats: number) =>
  String(Math.round(beats * 100) / 100).replace('.', ',')

/** Qué impide guardar este riff, o null si está bien (mismas reglas que la API). */
export function riffProblem(
  events: readonly NoteEvent[],
  lengthBeats: number,
): string | null {
  if (events.length === 0)
    return 'El riff necesita al menos una nota. Para quitarlo, volvé a la automática.'
  const end = Math.max(...events.map((event) => event.t + event.dur))
  if (end > lengthBeats + LENGTH_TOLERANCE) {
    return `El riff se pasa de la sección: termina en el beat ${beatsText(end)} y la sección dura ${beatsText(lengthBeats)} beats.`
  }
  return null
}

/** Arma el riff para el chart: el `bpm` es siempre el del chart (ADR 0018). */
export function buildRiff(
  base: Notation | null | undefined,
  bpm: number,
  events: readonly NoteEvent[],
): Notation {
  return { ...base, bpm, events: events.map((event) => ({ ...event })) }
}
