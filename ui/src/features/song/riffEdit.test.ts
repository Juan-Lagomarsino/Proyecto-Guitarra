import { describe, expect, it } from 'vitest'
import type { NoteEvent } from '../../notation/types'
import type { SongChartContent } from '../../songs/types'
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
  riffProblem,
  sectionLengthBeats,
  selectNote,
  startDraft,
  undo,
} from './riffEdit'

const events = (): NoteEvent[] => [
  { t: 0, dur: 1, string: 5, fret: 3, confidence: 0.9 },
  { t: 1, dur: 1, string: 4, fret: 5, confidence: 0.4 },
]

const selected = (index = 0) => selectNote(startDraft(events()), index)

describe('selección', () => {
  it('elige una nota y deja elegir ninguna', () => {
    expect(selected(1).selected).toBe(1)
    expect(selectNote(selected(1), null).selected).toBeNull()
  })
  it('ignora un índice que no existe', () => {
    expect(selectNote(startDraft(events()), 9).selected).toBeNull()
  })
  it('elegir no entra en el historial', () => {
    expect(canUndo(selected())).toBe(false)
  })
})

describe('traste', () => {
  it('cambia el traste y la nota pasa a ser del usuario (sin confidence)', () => {
    const draft = changeFret(selected(), 7)
    expect(draft.events[0]).toEqual({ t: 0, dur: 1, string: 5, fret: 7 })
    expect(draft.events[1].confidence).toBe(0.4)
  })
  it.each([-1, 23, 2.5, Number.NaN])('rechaza el traste %s', (fret) => {
    const draft = changeFret(selected(), fret)
    expect(draft.events[0].fret).toBe(3)
    expect(draft.warning).toMatch(/0 y 22/)
  })
  it('acepta los bordes 0 y 22', () => {
    expect(changeFret(selected(), 0).events[0].fret).toBe(0)
    expect(changeFret(selected(), 22).events[0].fret).toBe(22)
  })
  it('sin nota elegida no hace nada', () => {
    const draft = startDraft(events())
    expect(changeFret(draft, 4)).toBe(draft)
  })
})

describe('cuerda manteniendo la altura', () => {
  it('A traste 3 (C3) pasa a la cuerda 6 en el traste 8', () => {
    const draft = changeStringKeepingPitch(selected(), 6)
    expect(draft.events[0]).toMatchObject({ string: 6, fret: 8 })
    expect(draft.events[0].confidence).toBeUndefined()
  })
  it('hacia una cuerda más aguda baja el traste', () => {
    // cuerda 5 traste 7 = E3; en la cuerda 4 (D3) es el traste 2
    const draft = changeStringKeepingPitch(changeFret(selected(), 7), 4)
    expect(draft.events[0]).toMatchObject({ string: 4, fret: 2 })
  })
  it('si no se puede (traste negativo) avisa y no cambia', () => {
    const draft = changeStringKeepingPitch(selected(), 1)
    expect(draft.events[0]).toMatchObject({ string: 5, fret: 3 })
    expect(draft.events[0].confidence).toBe(0.9)
    expect(draft.warning).toMatch(/no existe en la cuerda 1/i)
  })
  it('si pasa del traste 22 avisa y no cambia', () => {
    const base = selectNote(
      startDraft([{ t: 0, dur: 1, string: 1, fret: 20 }]),
      0,
    )
    const draft = changeStringKeepingPitch(base, 6)
    expect(draft.events[0].string).toBe(1)
    expect(draft.warning).not.toBeNull()
  })
  it('respeta una afinación distinta (drop D)', () => {
    const tuning: [string, string, string, string, string, string] = [
      'D2',
      'A2',
      'D3',
      'G3',
      'B3',
      'E4',
    ]
    const base = selectNote(
      startDraft([{ t: 0, dur: 1, string: 6, fret: 2 }], tuning),
      0,
    )
    // E2 en la cuerda 5 (A2) no existe: avisa
    expect(changeStringKeepingPitch(base, 5).warning).not.toBeNull()
  })
  it('la misma cuerda no cambia nada', () => {
    const draft = selected()
    expect(changeStringKeepingPitch(draft, 5)).toBe(draft)
  })
  it('avisa si ya hay una nota en esa cuerda en el mismo beat', () => {
    const base = selectNote(
      startDraft([
        { t: 0, dur: 1, string: 5, fret: 3 },
        { t: 0, dur: 1, string: 6, fret: 8 },
      ]),
      0,
    )
    const draft = changeStringKeepingPitch(base, 6)
    expect(draft.events[0].string).toBe(5)
    expect(draft.warning).toMatch(/ya hay una nota/i)
  })
})

describe('cuerda con traste libre', () => {
  it('cambia la cuerda y deja el traste', () => {
    const draft = changeStringFree(selected(), 2)
    expect(draft.events[0]).toMatchObject({ string: 2, fret: 3 })
  })
  it('rechaza cuerdas fuera de 1–6', () => {
    expect(changeStringFree(selected(), 7).events[0].string).toBe(5)
    expect(changeStringFree(selected(), 0).warning).not.toBeNull()
  })
})

describe('técnica y bend', () => {
  it('pone una técnica', () => {
    expect(changeTechnique(selected(), 'h').events[0].technique).toBe('h')
  })
  it('bend arranca en 1 semitono y se puede cambiar', () => {
    const bent = changeTechnique(selected(), 'b')
    expect(bent.events[0]).toMatchObject({ technique: 'b', bend: 1 })
    expect(changeBend(bent, 2).events[0].bend).toBe(2)
  })
  it('al sacar el bend se borra el campo bend', () => {
    const bent = changeTechnique(selected(), 'b')
    const plain = changeTechnique(bent, 'h')
    expect(plain.events[0].bend).toBeUndefined()
    expect(changeTechnique(bent, null).events[0].technique).toBeUndefined()
  })
  it('bend solo vale con la técnica b y en (0, 4]', () => {
    expect(changeBend(selected(), 1).warning).not.toBeNull()
    const bent = changeTechnique(selected(), 'b')
    expect(changeBend(bent, 0).events[0].bend).toBe(1)
    expect(changeBend(bent, 5).warning).not.toBeNull()
  })
  it('rechaza una técnica que no está en la lista', () => {
    const draft = changeTechnique(selected(), 'zz' as 'h')
    expect(draft.events[0].technique).toBeUndefined()
    expect(draft.warning).not.toBeNull()
  })
})

describe('duración', () => {
  it.each([0.25, 1 / 3, 0.5, 1, 2])('acepta %s', (dur) => {
    expect(changeDuration(selected(), dur).events[0].dur).toBe(dur)
  })
  it('rechaza valores fuera de la grilla', () => {
    const draft = changeDuration(selected(), 0.7)
    expect(draft.events[0].dur).toBe(1)
    expect(draft.warning).not.toBeNull()
  })
})

describe('agregar y borrar', () => {
  it('agrega una nota en el beat elegido, ordenada, y la deja elegida', () => {
    const draft = addNote(startDraft(events()), {
      t: 0.5,
      string: 3,
      fret: 2,
    })
    expect(draft.events.map((e) => e.t)).toEqual([0, 0.5, 1])
    expect(draft.events[1]).toEqual({ t: 0.5, dur: 1, string: 3, fret: 2 })
    expect(draft.selected).toBe(1)
  })
  it('usa la duración pedida', () => {
    const draft = addNote(startDraft([]), {
      t: 0,
      string: 1,
      fret: 0,
      dur: 0.5,
    })
    expect(draft.events[0].dur).toBe(0.5)
  })
  it('rechaza beat negativo, cuerda o traste inválidos', () => {
    const base = startDraft(events())
    expect(addNote(base, { t: -1, string: 1, fret: 0 }).events).toHaveLength(2)
    expect(addNote(base, { t: 0, string: 9, fret: 0 }).warning).not.toBeNull()
    expect(addNote(base, { t: 0, string: 1, fret: 30 }).warning).not.toBeNull()
  })
  it('rechaza una nota repetida en el mismo beat y cuerda', () => {
    const draft = addNote(startDraft(events()), { t: 0, string: 5, fret: 7 })
    expect(draft.events).toHaveLength(2)
    expect(draft.warning).toMatch(/ya hay una nota/i)
  })
  it('borra la elegida y deja sin selección', () => {
    const draft = deleteSelected(selected(0))
    expect(draft.events).toHaveLength(1)
    expect(draft.events[0].fret).toBe(5)
    expect(draft.selected).toBeNull()
  })
  it('borrar sin selección no hace nada', () => {
    const base = startDraft(events())
    expect(deleteSelected(base)).toBe(base)
  })
})

describe('deshacer', () => {
  it('vuelve atrás varios pasos y restaura la selección', () => {
    let draft = selected(0)
    draft = changeFret(draft, 7)
    draft = changeTechnique(draft, 'h')
    draft = deleteSelected(draft)
    expect(draft.events).toHaveLength(1)
    draft = undo(draft)
    expect(draft.events[0]).toMatchObject({ fret: 7, technique: 'h' })
    expect(draft.selected).toBe(0)
    draft = undo(undo(draft))
    expect(draft.events).toEqual(events())
    expect(canUndo(draft)).toBe(false)
  })
  it('deshacer una nota agregada la quita', () => {
    const added = addNote(startDraft(events()), { t: 2, string: 1, fret: 0 })
    expect(undo(added).events).toEqual(events())
  })
  it('un cambio rechazado no entra en el historial', () => {
    expect(canUndo(changeFret(selected(), 99))).toBe(false)
  })
  it('sin historial no hace nada', () => {
    const base = startDraft(events())
    expect(undo(base)).toBe(base)
  })
  it('no muta los eventos originales', () => {
    const original = events()
    const draft = changeFret(selectNote(startDraft(original), 0), 9)
    expect(original[0].fret).toBe(3)
    expect(draft.events).not.toBe(original)
  })
})

describe('largo contra la sección', () => {
  const chart = (grid?: number[]) =>
    ({
      instrument: 'electric',
      bpm: 120,
      beat_grid: grid ? { beats_s: grid } : undefined,
      sections: [{ id: 'a', name: 'A', start_s: 10, end_s: 14, order: 0 }],
    }) as unknown as SongChartContent

  it('sin grilla usa segundos por bpm del chart', () => {
    expect(sectionLengthBeats(chart(), chart().sections[0])).toBe(8)
  })
  it('con grilla cuenta los beats entre inicio y fin', () => {
    // un beat cada 0,5 s desde 0: 4 s = 8 beats
    const grid = Array.from({ length: 41 }, (_, i) => i * 0.5)
    const content = chart(grid)
    expect(sectionLengthBeats(content, content.sections[0])).toBeCloseTo(8)
  })
  it('con grilla irregular interpola', () => {
    // beats a 0, 1, 3, 5: del segundo 1 al 5 hay 2 beats
    const content = chart([0, 1, 3, 5])
    const section = { ...content.sections[0], start_s: 1, end_s: 5 }
    expect(sectionLengthBeats(content, section)).toBeCloseTo(2)
  })
  it('un riff que entra no tiene problema', () => {
    expect(riffProblem([{ t: 7, dur: 1, string: 1, fret: 0 }], 8)).toBeNull()
  })
  it('tolera 0,01 beats', () => {
    expect(riffProblem([{ t: 7, dur: 1.01, string: 1, fret: 0 }], 8)).toBeNull()
  })
  it('un riff que se pasa dice cuánto', () => {
    const problem = riffProblem([{ t: 7.5, dur: 1, string: 1, fret: 0 }], 8)
    expect(problem).toMatch(/se pasa/)
    expect(problem).toMatch(/8/)
  })
  it('un riff vacío no se guarda', () => {
    expect(riffProblem([], 8)).toMatch(/al menos una nota/)
  })
})

describe('buildRiff', () => {
  it('copia el bpm del chart y conserva el resto del riff base', () => {
    const base = { bpm: 99, tuning: ['D2', 'A2', 'D3', 'G3', 'B3', 'E4'] }
    const riff = buildRiff(base as never, 120, events())
    expect(riff.bpm).toBe(120)
    expect(riff.tuning?.[0]).toBe('D2')
    expect(riff.events).toHaveLength(2)
  })
  it('crea desde cero sin base', () => {
    expect(buildRiff(null, 90, events())).toEqual({
      bpm: 90,
      events: events(),
    })
  })
})
