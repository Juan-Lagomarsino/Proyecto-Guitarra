import { useCallback, useEffect, useRef, useState } from 'react'
import { withToken } from '../../api/client'
import type { SongDetail } from '../../api/songs'
import { usePublishBacking } from '../../backing/BackingContext'
import {
  defaultBackingFactory,
  type BackingChoice,
  type BackingFactory,
} from '../../backing/factory'
import { isValidLoop } from '../../backing/loop'
import type { BackingSource } from '../../backing/types'
import type { ChartSection, SongChartContent } from '../../songs/types'
import {
  noGuitarAvailability,
  originalAvailability,
  type BackingGroup,
  type OptionAvailability,
} from './backingOptions'
import './backing.css'

const MIN_PERCENT = 50
const MAX_PERCENT = 100
const STEP_PERCENT = 5

type MetronomeKind = 'click' | 'drums'

const AUTOPLAY_BLOCKED =
  'El navegador bloqueó el audio. Tocá reproducir de nuevo para activarlo.'
const PLAY_FAILED = 'No se pudo reproducir el acompañamiento.'

function playErrorMessage(error: unknown): string {
  const blocked =
    error instanceof DOMException && error.name === 'NotAllowedError'
  return blocked ? AUTOPLAY_BLOCKED : PLAY_FAILED
}

function choiceOf(
  group: BackingGroup,
  metronome: MetronomeKind,
): BackingChoice {
  if (group === 'metronome') return metronome
  return group === 'generated' ? 'full' : group
}

interface OptionDef {
  group: BackingGroup
  label: string
  hint?: string
  experimental?: boolean
}

const OPTIONS: OptionDef[] = [
  { group: 'metronome', label: 'Metrónomo / batería' },
  { group: 'original', label: 'Original' },
  { group: 'no_guitar', label: 'Sin guitarra', experimental: true },
  {
    group: 'generated',
    label: 'Backing generado',
    hint: 'batería + bajo + acordes',
  },
]

function applyLoop(
  source: BackingSource,
  active: boolean,
  startS: number,
  endS: number,
): void {
  const range = { startS, endS }
  source.setLoop(active && isValidLoop(range) ? range : null)
}

interface BackingPanelProps {
  song: SongDetail
  content: SongChartContent
  /** Sección elegida en la línea de tiempo: es la que se repite con el loop. */
  selected: ChartSection
  /** Avisa qué sección está en loop (o `null`) para marcarla en la línea de tiempo. */
  onLoopChange?: (sectionId: string | null) => void
  factory?: BackingFactory
}

export function BackingPanel({
  song,
  content,
  selected,
  onLoopChange,
  factory = defaultBackingFactory,
}: BackingPanelProps) {
  const { setSource: publish, setPosition: publishPosition } =
    usePublishBacking()
  const [group, setGroup] = useState<BackingGroup>('metronome')
  const [metronome, setMetronome] = useState<MetronomeKind>('click')
  const [percent, setPercent] = useState(MAX_PERCENT)
  const [loopOn, setLoopOn] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<BackingSource | null>(null)
  const positionRef = useRef(0)

  const availability: Record<BackingGroup, OptionAvailability> = {
    metronome: { url: null, disabledReason: null },
    generated: { url: null, disabledReason: null },
    original: originalAvailability(song),
    no_guitar: noGuitarAvailability(song),
  }

  const retire = useCallback((): boolean => {
    const old = sourceRef.current
    if (old === null) return false
    positionRef.current = old.position()
    const wasPlaying = old.isPlaying()
    old.pause()
    old.dispose()
    sourceRef.current = null
    publish(null)
    publishPosition(positionRef.current)
    return wasPlaying
  }, [publish, publishPosition])

  const build = (nextGroup: BackingGroup, nextMetronome: MetronomeKind) => {
    const url = availability[nextGroup].url
    const source = factory({
      choice: choiceOf(nextGroup, nextMetronome),
      content,
      mediaUrl: url === null ? null : withToken(url),
    })
    source.setRate(percent / 100)
    applyLoop(source, loopOn, selected.start_s, selected.end_s)
    source.seek(positionRef.current)
    source.onEnded(() => setPlaying(false))
    sourceRef.current = source
    publish(source)
    return source
  }

  const reportPlayFailure = (failure: unknown) => {
    setPlaying(false)
    setError(playErrorMessage(failure))
  }

  /** Arma (si hace falta) la fuente y la reproduce; todo error de play llega a `reportPlayFailure`. */
  const launch = (open: () => BackingSource) => {
    setPlaying(true)
    setError(null)
    const run = async () => {
      await open().play()
    }
    run().catch(reportPlayFailure)
  }

  const choose = (nextGroup: BackingGroup, nextMetronome: MetronomeKind) => {
    setGroup(nextGroup)
    setMetronome(nextMetronome)
    const wasPlaying = retire()
    if (!wasPlaying && !playing) return
    launch(() => build(nextGroup, nextMetronome))
  }

  const togglePlay = () => {
    const current = sourceRef.current
    if (playing && current) {
      current.pause()
      positionRef.current = current.position()
      publishPosition(positionRef.current)
      setPlaying(false)
      return
    }
    launch(() => current ?? build(group, metronome))
  }

  const changeSpeed = (value: number) => {
    setPercent(value)
    sourceRef.current?.setRate(value / 100)
  }

  const { start_s: startS, end_s: endS } = selected

  // El loop sigue a la sección elegida mientras esté activado.
  useEffect(() => {
    const source = sourceRef.current
    if (source === null) {
      // Sin fuente viva, el salto al inicio del loop igual se publica.
      if (loopOn) {
        positionRef.current = startS
        publishPosition(startS)
      }
      return
    }
    applyLoop(source, loopOn, startS, endS)
    if (loopOn) source.seek(startS)
  }, [loopOn, startS, endS, publishPosition])

  useEffect(() => {
    onLoopChange?.(loopOn ? selected.id : null)
  }, [loopOn, selected.id, onLoopChange])

  useEffect(
    () => () => {
      sourceRef.current?.dispose()
      sourceRef.current = null
    },
    [],
  )

  const resultingBpm = Math.round((content.bpm * percent) / 100)

  return (
    <section className="backing" aria-label="Acompañamiento">
      <h3 className="progress-subtitle">Acompañamiento</h3>

      <div className="backing__options" role="radiogroup" aria-label="Fuente">
        {OPTIONS.map(({ group: value, label, hint, experimental }) => {
          const { disabledReason } = availability[value]
          return (
            <label
              key={value}
              className="backing__option"
              data-disabled={disabledReason !== null}
            >
              <input
                type="radio"
                name="backing-source"
                checked={group === value}
                disabled={disabledReason !== null}
                onChange={() => choose(value, metronome)}
              />
              <span className="backing__option-text">
                <span className="backing__option-label">
                  {label}
                  {experimental && (
                    <span className="backing__chip">experimental</span>
                  )}
                </span>
                {hint && <span className="backing__hint">{hint}</span>}
                {disabledReason && (
                  <span className="backing__hint">{disabledReason}</span>
                )}
              </span>
            </label>
          )
        })}
      </div>

      {group === 'metronome' && (
        <div className="backing__sub" role="group" aria-label="Metrónomo">
          {(
            [
              ['click', 'Clic'],
              ['drums', 'Batería'],
            ] as const
          ).map(([kind, label]) => (
            <button
              key={kind}
              type="button"
              className="explore-mode"
              aria-pressed={metronome === kind}
              onClick={() => choose('metronome', kind)}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      <div className="backing__speed">
        <label htmlFor="backing-speed">Velocidad</label>
        <input
          id="backing-speed"
          type="range"
          min={MIN_PERCENT}
          max={MAX_PERCENT}
          step={STEP_PERCENT}
          value={percent}
          onChange={(event) => changeSpeed(Number(event.target.value))}
        />
        <span className="backing__speed-value">{percent} %</span>
        <span className="backing__bpm">{resultingBpm} BPM</span>
      </div>

      <div className="backing__transport">
        <button type="button" className="explore-submit" onClick={togglePlay}>
          {playing ? 'Pausar' : 'Reproducir'}
        </button>
        <button
          type="button"
          className="explore-mode"
          aria-pressed={loopOn}
          onClick={() => setLoopOn((on) => !on)}
        >
          Repetir sección: {selected.name}
        </button>
      </div>

      {error && (
        <p className="backing__error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
