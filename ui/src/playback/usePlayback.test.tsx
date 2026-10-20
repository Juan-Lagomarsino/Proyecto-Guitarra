import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Notation } from '../notation/types'
import { FakeAudio } from './fakeClock'
import { usePlayback } from './usePlayback'

const notation: Notation = {
  bpm: 120,
  events: [
    { t: 0, dur: 1, string: 6, fret: 0 },
    { t: 1, dur: 1, string: 5, fret: 2 },
  ],
}

function setup() {
  const audio = new FakeAudio()
  const factory = () => audio // identidad estable entre renders
  const hook = renderHook(() =>
    usePlayback(notation, { audio: factory, metronome: true }),
  )
  return { audio, clock: audio.clock, ...hook }
}

describe('usePlayback', () => {
  it('expone el contrato y avanza con el reloj', () => {
    const { clock, result } = setup()
    expect(result.current.activeIndex).toBeNull()
    expect(result.current.mode).toBe('auto')
    expect(result.current.bpm).toBe(120)

    act(() => result.current.play())
    expect(result.current.isPlaying).toBe(true)
    act(() => clock.advance(0.6))
    expect(result.current.activeIndex).toBe(1)
    act(() => result.current.setBpm(90))
    expect(result.current.bpm).toBe(90)
    act(() => result.current.pause())
    expect(result.current.isPlaying).toBe(false)
    act(() => result.current.stop())
    expect(result.current.activeIndex).toBeNull()
  })

  it('nota por nota con next y prev', () => {
    const { result } = setup()
    act(() => result.current.setMode('step'))
    act(() => result.current.next())
    expect(result.current.activeIndex).toBe(0)
    act(() => result.current.next())
    expect(result.current.activeIndices).toEqual([1])
    act(() => result.current.prev())
    expect(result.current.activeIndex).toBe(0)
  })

  it('al desmontar cierra el contexto de audio y los timers', () => {
    const { audio, clock, result, unmount } = setup()
    act(() => result.current.play())
    act(() => clock.advance(0.2))
    expect(clock.activeTimers).toBeGreaterThan(0)
    unmount()
    expect(audio.closed).toBe(1)
    expect(clock.activeTimers).toBe(0)
  })
})
