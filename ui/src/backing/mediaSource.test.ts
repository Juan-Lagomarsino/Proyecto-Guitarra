import { describe, expect, it } from 'vitest'
import { FakeClock } from '../playback/fakeClock'
import { MediaBackingSource, type MediaLike } from './mediaSource'

class FakeMedia implements MediaLike {
  currentTime = 0
  duration = 60
  paused = true
  playbackRate = 1
  preservesPitch = false
  mozPreservesPitch = false
  webkitPreservesPitch = false
  private endedListeners = new Set<() => void>()

  play(): Promise<void> {
    this.paused = false
    return Promise.resolve()
  }
  pause(): void {
    this.paused = true
  }
  addEventListener(_type: 'ended', fn: () => void): void {
    this.endedListeners.add(fn)
  }
  removeEventListener(_type: 'ended', fn: () => void): void {
    this.endedListeners.delete(fn)
  }
  fireEnded(): void {
    this.paused = true
    this.endedListeners.forEach((fn) => fn())
  }
}

function setup() {
  const media = new FakeMedia()
  const clock = new FakeClock()
  const source = new MediaBackingSource(media, clock)
  return { media, clock, source }
}

describe('MediaBackingSource', () => {
  it('acota la velocidad a [0,5; 1,0]', () => {
    const { media, source } = setup()
    source.setRate(0.2)
    expect(media.playbackRate).toBe(0.5)
    source.setRate(2)
    expect(media.playbackRate).toBe(1)
    source.setRate(0.75)
    expect(media.playbackRate).toBe(0.75)
  })

  it('mantiene preservesPitch en true con prefijos, también tras cambiar la velocidad', () => {
    const { media, source } = setup()
    expect(media.preservesPitch).toBe(true)
    expect(media.mozPreservesPitch).toBe(true)
    expect(media.webkitPreservesPitch).toBe(true)
    media.preservesPitch = false
    source.setRate(0.5)
    expect(media.preservesPitch).toBe(true)
  })

  it('play/pause/isPlaying reflejan el media', () => {
    const { media, source } = setup()
    source.play()
    expect(source.isPlaying()).toBe(true)
    expect(media.paused).toBe(false)
    source.pause()
    expect(source.isPlaying()).toBe(false)
  })

  it('position lee currentTime; seek lo acota', () => {
    const { media, source } = setup()
    source.seek(12)
    expect(source.position()).toBe(12)
    source.seek(-3)
    expect(media.currentTime).toBe(0)
    source.seek(500)
    expect(media.currentTime).toBe(60)
  })

  it('loop A-B: al pasar B vuelve a A', () => {
    const { media, clock, source } = setup()
    source.setLoop({ startS: 10, endS: 20 })
    source.play()
    media.currentTime = 19.9
    clock.advance(0.05)
    expect(media.currentTime).toBe(19.9)
    media.currentTime = 20.1
    clock.advance(0.05)
    expect(media.currentTime).toBe(10)
  })

  it('rechaza un loop con A >= B o fuera de la duración y conserva el anterior', () => {
    const { media, clock, source } = setup()
    source.setLoop({ startS: 10, endS: 20 })
    expect(() => source.setLoop({ startS: 5, endS: 5 })).toThrow()
    expect(() => source.setLoop({ startS: 5, endS: 61 })).toThrow()
    media.currentTime = 21
    clock.advance(0.05)
    expect(media.currentTime).toBe(10)
  })

  it('sacar el loop sigue de largo', () => {
    const { media, clock, source } = setup()
    source.setLoop({ startS: 10, endS: 20 })
    source.setLoop(null)
    media.currentTime = 25
    clock.advance(0.05)
    expect(media.currentTime).toBe(25)
  })

  it('seek dentro del loop no lo rompe; fuera, el loop devuelve a A al pasar B', () => {
    const { media, clock, source } = setup()
    source.setLoop({ startS: 10, endS: 20 })
    source.seek(15)
    clock.advance(0.05)
    expect(media.currentTime).toBe(15)
    source.seek(30)
    clock.advance(0.05)
    expect(media.currentTime).toBe(10)
  })

  it('onEnded avisa y se puede cancelar', () => {
    const { media, source } = setup()
    let calls = 0
    const off = source.onEnded(() => calls++)
    media.fireEnded()
    expect(calls).toBe(1)
    off()
    media.fireEnded()
    expect(calls).toBe(1)
  })

  it('loop que termina en la duración: al llegar el ended vuelve a A y sigue sonando', () => {
    const { media, source } = setup()
    let ended = 0
    source.onEnded(() => ended++)
    source.setLoop({ startS: 50, endS: 60 })
    source.play()
    media.currentTime = 60
    media.fireEnded()
    expect(media.currentTime).toBe(50)
    expect(media.paused).toBe(false)
    expect(ended).toBe(0)
  })

  it('seek con NaN o Infinity se ignora', () => {
    const { media, source } = setup()
    source.seek(7)
    source.seek(Number.NaN)
    source.seek(Number.POSITIVE_INFINITY)
    source.seek(Number.NEGATIVE_INFINITY)
    expect(media.currentTime).toBe(7)
  })

  it('dispose cancela el onFrame, pausa y deja de saltar', () => {
    const { media, clock, source } = setup()
    expect(clock.activeTimers).toBe(1)
    source.setLoop({ startS: 10, endS: 20 })
    source.dispose()
    expect(clock.activeTimers).toBe(0)
    expect(media.paused).toBe(true)
    media.currentTime = 25
    clock.advance(0.1)
    expect(media.currentTime).toBe(25)
  })
})
