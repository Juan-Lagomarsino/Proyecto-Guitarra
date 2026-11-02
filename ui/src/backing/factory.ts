import type { SongChartContent } from '../songs/types'
import { AudioContextClock } from '../playback/webAudio'
import { GeneratedBackingSource, type GeneratedMode } from './generatedSource'
import { MediaBackingSource } from './mediaSource'
import { WebAudioVoiceSink } from './synth'
import type { BackingSource } from './types'

/** Qué suena: clic, batería, el audio original, la mezcla sin guitarra o el backing completo. */
export type BackingChoice = GeneratedMode | 'original' | 'no_guitar'

export interface BackingRequest {
  choice: BackingChoice
  content: SongChartContent
  /** URL ya con token; solo para `original` y `no_guitar`. */
  mediaUrl: string | null
}

/** Arma la fuente. Se inyecta en el panel para poder probarlo sin audio real. */
export type BackingFactory = (request: BackingRequest) => BackingSource

interface SharedAudio {
  ctx: AudioContext
  clock: AudioContextClock
}

let shared: SharedAudio | null = null

/**
 * Un solo AudioContext y un solo reloj para toda la página. Se crea al
 * armar la primera fuente, que siempre ocurre dentro de un clic del
 * usuario (política de autoplay).
 */
function sharedAudio(): SharedAudio {
  if (shared === null) {
    const ctx = new AudioContext()
    shared = { ctx, clock: new AudioContextClock(ctx) }
  }
  void shared.ctx.resume()
  return shared
}

export const defaultBackingFactory: BackingFactory = ({
  choice,
  content,
  mediaUrl,
}) => {
  const { ctx, clock } = sharedAudio()
  if (choice === 'original' || choice === 'no_guitar') {
    if (mediaUrl === null) throw new Error('Falta la URL del audio.')
    const media = new Audio(mediaUrl)
    media.preload = 'auto'
    return new MediaBackingSource(media, clock)
  }
  return new GeneratedBackingSource({
    content,
    mode: choice,
    clock,
    sink: new WebAudioVoiceSink(ctx),
  })
}
