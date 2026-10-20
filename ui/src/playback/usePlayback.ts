import { useEffect, useMemo, useSyncExternalStore } from 'react'
import type { Notation } from '../notation/types'
import type { PlaybackAudio } from './clock'
import { PlaybackEngine, type PlaybackMode } from './engine'
import { createWebAudio } from './webAudio'

export type { PlaybackMode } from './engine'

export interface PlaybackOptions {
  /** BPM inicial (por defecto el de la notación). Para cambiarlo en vivo usar `setBpm`; cambiar esta opción recrea el motor. */
  bpm?: number
  metronome?: boolean
  countIn?: boolean
  /** Solo para tests: audio inyectado (con identidad estable) en lugar de Web Audio. */
  audio?: () => PlaybackAudio
}

export interface PlaybackControls {
  activeIndex: number | null
  activeIndices: number[]
  isPlaying: boolean
  mode: PlaybackMode
  bpm: number
  setBpm: (bpm: number) => void
  play: () => void
  pause: () => void
  stop: () => void
  next: () => void
  prev: () => void
  setMode: (mode: PlaybackMode) => void
}

/**
 * Reproducción del ejercicio. `options.bpm` es solo el valor inicial: para
 * cambiarlo en vivo se usa `setBpm`. Al desmontar se cierra el audio.
 */
export function usePlayback(
  notation: Notation,
  options: PlaybackOptions = {},
): PlaybackControls {
  const {
    bpm: initialBpm,
    metronome = false,
    countIn = false,
    audio = createWebAudio,
  } = options

  const engine = useMemo(
    () =>
      new PlaybackEngine(notation, {
        audio,
        bpm: initialBpm,
      }),
    [notation, audio, initialBpm],
  )

  useEffect(() => {
    engine.setMetronome(metronome)
    engine.setCountIn(countIn)
  }, [engine, metronome, countIn])

  useEffect(() => () => engine.dispose(), [engine])

  const snapshot = useSyncExternalStore(engine.subscribe, engine.getSnapshot)

  return {
    ...snapshot,
    setBpm: (value) => engine.setBpm(value),
    play: () => engine.play(),
    pause: () => engine.pause(),
    stop: () => engine.stop(),
    next: () => engine.next(),
    prev: () => engine.prev(),
    setMode: (mode) => engine.setMode(mode),
  }
}
