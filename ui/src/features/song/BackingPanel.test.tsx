import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import type { SongDetail } from '../../api/songs'
import { BackingProvider, useBacking } from '../../backing/BackingContext'
import type { BackingFactory } from '../../backing/factory'
import type { BackingSource } from '../../backing/types'
import type { ChartSection, SongChartContent } from '../../songs/types'
import { BackingPanel } from './BackingPanel'
import css from './backing.css?raw'

class FakeSource implements BackingSource {
  pos = 0
  playing = false
  play = vi.fn((): Promise<void> => {
    this.playing = true
    return Promise.resolve()
  })
  pause = vi.fn(() => {
    this.playing = false
  })
  seek = vi.fn((s: number) => {
    this.pos = s
  })
  position = () => this.pos
  setRate = vi.fn()
  setLoop = vi.fn()
  isPlaying = () => this.playing
  onEnded = vi.fn(() => () => undefined)
  dispose = vi.fn()
}

const chartSection = (id: string, start: number, end: number): ChartSection =>
  ({
    id,
    name: id,
    start_s: start,
    end_s: end,
    order: 0,
    chord_source: 'detected',
    chords: [],
  }) as unknown as ChartSection

const intro = chartSection('intro', 0, 20)
const verse = chartSection('estrofa', 20, 60)
const content = {
  instrument: 'classical',
  bpm: 80,
  sections: [intro, verse],
} as unknown as SongChartContent

const song = (over: Partial<SongDetail> = {}): SongDetail =>
  ({
    id: 7,
    audio: [
      {
        kind: 'original',
        format: 'mp3',
        url: '/api/v1/songs/7/audio/original',
      },
    ],
    separation_status: 'none',
    ...over,
  }) as SongDetail

let sources: FakeSource[]
let factory: ReturnType<typeof vi.fn<BackingFactory>>

beforeEach(() => {
  sources = []
  factory = vi.fn<BackingFactory>(() => {
    const source = new FakeSource()
    sources.push(source)
    return source
  })
})

function SourceProbe() {
  const { source, position } = useBacking()
  return (
    <>
      <output aria-label="fuente">{source ? 'activa' : 'ninguna'}</output>
      <output aria-label="posición">{position}</output>
    </>
  )
}

function Harness({ detail = song() }: { detail?: SongDetail }) {
  const [selected, setSelected] = useState(intro)
  return (
    <BackingProvider>
      <button onClick={() => setSelected(verse)}>elegir estrofa</button>
      <BackingPanel
        song={detail}
        content={content}
        selected={selected}
        factory={factory}
      />
      <SourceProbe />
    </BackingProvider>
  )
}

const option = (name: RegExp) => screen.getByRole('radio', { name })
const playButton = () => screen.getByRole('button', { name: /reproducir/i })

describe('BackingPanel opciones', () => {
  it('muestra las 4 opciones', () => {
    render(<Harness />)
    expect(option(/metrónomo/i)).toBeInTheDocument()
    expect(option(/original/i)).toBeInTheDocument()
    expect(option(/sin guitarra/i)).toBeInTheDocument()
    expect(option(/generado/i)).toBeInTheDocument()
    expect(screen.getByText(/experimental/i)).toBeInTheDocument()
  })

  it.each([
    ['queued', /separando/i],
    ['running', /separando/i],
    ['error', /no se pudo separar/i],
    ['none', /no disponible/i],
    ['done', /no disponible/i],
  ] as const)(
    'sin guitarra deshabilitado con motivo (%s)',
    (status, reason) => {
      render(<Harness detail={song({ separation_status: status })} />)
      expect(option(/sin guitarra/i)).toBeDisabled()
      expect(screen.getByText(reason)).toBeInTheDocument()
    },
  )

  it('sin guitarra se habilita si hay asset', () => {
    const audio = [
      {
        kind: 'no_guitar',
        format: 'mp3',
        url: '/api/v1/songs/7/audio/no_guitar',
      },
    ]
    render(<Harness detail={song({ audio, separation_status: 'done' })} />)
    expect(option(/sin guitarra/i)).toBeEnabled()
  })

  it('original deshabilitado sin asset original', () => {
    render(<Harness detail={song({ audio: [] })} />)
    expect(option(/original/i)).toBeDisabled()
    expect(screen.getAllByText(/no disponible/i).length).toBeGreaterThan(0)
  })

  it('al tocar crea la fuente con la opción, el contenido y la url con token', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(option(/original/i))
    await user.click(playButton())
    expect(factory).toHaveBeenCalledTimes(1)
    const request = factory.mock.calls[0][0]
    expect(request.choice).toBe('original')
    expect(request.content).toBe(content)
    expect(request.mediaUrl).toMatch(/\/songs\/7\/audio\/original\?token=/)
    expect(sources[0].play).toHaveBeenCalled()
  })

  it('metrónomo tiene sub-selector clic / batería y el generado usa full', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Batería' }))
    await user.click(playButton())
    expect(factory.mock.calls[0][0].choice).toBe('drums')
    await user.click(option(/generado/i))
    expect(factory.mock.calls[1][0].choice).toBe('full')
  })
})

describe('BackingPanel transporte', () => {
  it('play y pausa', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    await user.click(screen.getByRole('button', { name: /pausar/i }))
    expect(sources[0].pause).toHaveBeenCalled()
    expect(playButton()).toBeInTheDocument()
  })

  it('muestra un mensaje legible si play falla por autoplay', async () => {
    const user = userEvent.setup()
    factory.mockImplementation(() => {
      const source = new FakeSource()
      source.play.mockImplementation(() => {
        throw new DOMException('bloqueado', 'NotAllowedError')
      })
      return source
    })
    render(<Harness />)
    await user.click(playButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /el navegador bloqueó el audio/i,
    )
    expect(playButton()).toBeInTheDocument()
  })

  it('muestra el error de autoplay cuando play rechaza de forma asíncrona', async () => {
    const user = userEvent.setup()
    factory.mockImplementation(() => {
      const source = new FakeSource()
      source.play.mockImplementation(() =>
        Promise.reject(new DOMException('bloqueado', 'NotAllowedError')),
      )
      return source
    })
    render(<Harness />)
    await user.click(option(/original/i))
    await user.click(playButton())
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /el navegador bloqueó el audio/i,
    )
    expect(playButton()).toBeInTheDocument()
  })

  it('cambiar de opción para la fuente anterior y conserva la posición', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    sources[0].pos = 12.5
    await user.click(option(/generado/i))
    expect(sources[0].pause).toHaveBeenCalled()
    expect(sources[0].dispose).toHaveBeenCalled()
    expect(sources[1].seek).toHaveBeenCalledWith(12.5)
    expect(sources[1].play).toHaveBeenCalled()
  })

  it('al desmontar libera la fuente', async () => {
    const user = userEvent.setup()
    const { unmount } = render(<Harness />)
    await user.click(playButton())
    unmount()
    expect(sources[0].dispose).toHaveBeenCalled()
  })

  it('publica la última posición al pausar y al retirar la fuente', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    sources[0].pos = 7
    await user.click(screen.getByRole('button', { name: /pausar/i }))
    expect(screen.getByLabelText('posición')).toHaveTextContent('7')
    sources[0].pos = 9
    await user.click(option(/original/i))
    expect(screen.getByLabelText('fuente')).toHaveTextContent('ninguna')
    expect(screen.getByLabelText('posición')).toHaveTextContent('9')
  })

  it('el loop en pausa sin fuente publica el inicio de la sección', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'elegir estrofa' }))
    await user.click(screen.getByRole('button', { name: /repetir sección/i }))
    expect(screen.getByLabelText('fuente')).toHaveTextContent('ninguna')
    expect(screen.getByLabelText('posición')).toHaveTextContent('20')
  })

  it('expone la fuente activa por useBacking', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    expect(screen.getByLabelText('fuente')).toHaveTextContent('ninguna')
    await user.click(playButton())
    expect(screen.getByLabelText('fuente')).toHaveTextContent('activa')
  })
})

describe('BackingPanel velocidad', () => {
  it('va de 50 a 100 en pasos de 5 y muestra el BPM resultante', () => {
    render(<Harness />)
    const slider = screen.getByRole('slider', { name: /velocidad/i })
    expect(slider).toHaveAttribute('min', '50')
    expect(slider).toHaveAttribute('max', '100')
    expect(slider).toHaveAttribute('step', '5')
    expect(screen.getByText(/80 BPM/)).toBeInTheDocument()
    fireEvent.change(slider, { target: { value: '75' } })
    expect(screen.getByText('75 %')).toBeInTheDocument()
    expect(screen.getByText(/60 BPM/)).toBeInTheDocument()
  })

  it('aplica setRate a la fuente activa y a la nueva', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    fireEvent.change(screen.getByRole('slider', { name: /velocidad/i }), {
      target: { value: '70' },
    })
    expect(sources[0].setRate).toHaveBeenLastCalledWith(0.7)
    await user.click(option(/generado/i))
    expect(sources[1].setRate).toHaveBeenCalledWith(0.7)
  })
})

describe('BackingPanel loop por sección', () => {
  it('arma el loop de la sección elegida, lo sigue al cambiar y se saca', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    const toggle = screen.getByRole('button', { name: /repetir sección/i })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await user.click(toggle)
    expect(sources[0].setLoop).toHaveBeenLastCalledWith({ startS: 0, endS: 20 })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'elegir estrofa' }))
    expect(sources[0].setLoop).toHaveBeenLastCalledWith({
      startS: 20,
      endS: 60,
    })
    await user.click(toggle)
    expect(sources[0].setLoop).toHaveBeenLastCalledWith(null)
  })

  it('el loop se conserva al cambiar de opción', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(playButton())
    await user.click(screen.getByRole('button', { name: /repetir sección/i }))
    await user.click(option(/generado/i))
    expect(sources[1].setLoop).toHaveBeenCalledWith({ startS: 0, endS: 20 })
  })

  it('avisa a quien marque la línea de tiempo qué sección está en loop', async () => {
    const user = userEvent.setup()
    const onLoopChange = vi.fn()
    render(
      <BackingProvider>
        <BackingPanel
          song={song()}
          content={content}
          selected={intro}
          factory={factory}
          onLoopChange={onLoopChange}
        />
      </BackingProvider>,
    )
    await user.click(screen.getByRole('button', { name: /repetir sección/i }))
    expect(onLoopChange).toHaveBeenLastCalledWith('intro')
    await user.click(screen.getByRole('button', { name: /repetir sección/i }))
    expect(onLoopChange).toHaveBeenLastCalledWith(null)
  })
})

describe('BackingPanel layout', () => {
  it('el css se parte en líneas y no fija anchos (375 px sin scroll horizontal)', () => {
    expect(css).toMatch(/flex-wrap:\s*wrap/)
    expect(css).toMatch(/min-width:\s*0/)
    expect(css).not.toMatch(/(^|[^-])width:\s*\d{3,}px/)
  })
})
