import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CifraPanel } from './CifraPanel'

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

interface Call {
  method: string
  path: string
  body?: unknown
}

const mockApi = (
  reply: (call: Call) => Response = () =>
    json({ id: 7, reanalysis_queued: true }),
) => {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const call: Call = {
        method: init?.method ?? 'GET',
        path: url.replace('/api/v1', ''),
        body: init?.body ? JSON.parse(init.body as string) : undefined,
      }
      calls.push(call)
      return reply(call)
    }),
  )
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('CifraPanel', () => {
  it('sin cifra invita a cargarla y explica de dónde copiarla', () => {
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    expect(
      screen.getByRole('heading', { name: 'Cifra de Cifra Club' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Todavía no cargaste la cifra/)).toBeInTheDocument()
    expect(screen.getByText(/Copiá el texto de la cifra/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Cargar cifra' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Quitar' })).toBeNull()
  })

  it('con cifra muestra el estado, el link y los botones de reemplazar y quitar', () => {
    render(
      <CifraPanel
        songId={7}
        hasCifra
        cifraUrl="https://www.cifraclub.com.br/x/y/"
      />,
    )
    expect(screen.getByText(/Cifra cargada/)).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /cifraclub\.com\.br/ }),
    ).toHaveAttribute('href', 'https://www.cifraclub.com.br/x/y/')
    expect(
      screen.getByRole('button', { name: 'Reemplazar cifra' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Quitar' })).toBeInTheDocument()
  })

  it('guarda texto y link y avisa que se reanaliza', async () => {
    const user = userEvent.setup()
    const calls = mockApi()
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.type(screen.getByLabelText('Texto de la cifra'), '[[Intro] Am G')
    await user.type(
      screen.getByLabelText(/Link/),
      'https://www.cifraclub.com.br/x/',
    )
    await user.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(calls).toEqual([
      {
        method: 'PUT',
        path: '/songs/7/cifra',
        body: { text: '[Intro] Am G', url: 'https://www.cifraclub.com.br/x/' },
      },
    ])
    expect(await screen.findByRole('status')).toHaveTextContent(
      /Se está reanalizando/,
    )
    expect(screen.getByText(/Cifra cargada/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Texto de la cifra')).toBeNull()
  })

  it('manda url null si no se completa el link', async () => {
    const user = userEvent.setup()
    const calls = mockApi()
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.type(screen.getByLabelText('Texto de la cifra'), 'Am')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByRole('status')
    expect(calls[0]?.body).toEqual({ text: 'Am', url: null })
  })

  it('si ya había un análisis en curso avisa que se aplicará en el próximo', async () => {
    const user = userEvent.setup()
    mockApi(() => json({ id: 7, reanalysis_queued: false }))
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.type(screen.getByLabelText('Texto de la cifra'), 'Am')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('status')).toHaveTextContent(
      /análisis en curso/,
    )
  })

  it('no deja guardar con el texto vacío', async () => {
    const user = userEvent.setup()
    const calls = mockApi()
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    expect(screen.getByRole('button', { name: 'Guardar' })).toBeDisabled()
    expect(calls).toHaveLength(0)
  })

  it('muestra el error de la API y conserva lo escrito', async () => {
    const user = userEvent.setup()
    mockApi(() =>
      json({ detail: [{ loc: ['body', 'url'], msg: 'Link inválido' }] }, 422),
    )
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.type(screen.getByLabelText('Texto de la cifra'), 'Am')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByLabelText('Texto de la cifra')).toHaveValue('Am')
  })

  it('cancelar cierra el formulario sin llamar a la API', async () => {
    const user = userEvent.setup()
    const calls = mockApi()
    render(<CifraPanel songId={7} hasCifra={false} cifraUrl={null} />)
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    await user.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(screen.queryByLabelText('Texto de la cifra')).toBeNull()
    expect(calls).toHaveLength(0)
  })

  it('quita la cifra y vuelve al estado sin cargar', async () => {
    const user = userEvent.setup()
    const calls = mockApi(() => json(null, 204))
    render(<CifraPanel songId={7} hasCifra cifraUrl="https://c.com/x" />)
    await user.click(screen.getByRole('button', { name: 'Quitar' }))
    expect(calls).toEqual([
      { method: 'DELETE', path: '/songs/7/cifra', body: undefined },
    ])
    expect(
      await screen.findByText(/Todavía no cargaste la cifra/),
    ).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('avisa con onChanged después de guardar y de quitar', async () => {
    const user = userEvent.setup()
    mockApi()
    const onChanged = vi.fn()
    render(
      <CifraPanel
        songId={7}
        hasCifra={false}
        cifraUrl={null}
        onChanged={onChanged}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Cargar cifra' }))
    expect(onChanged).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('Texto de la cifra'), 'Am')
    await user.click(screen.getByRole('button', { name: 'Guardar' }))
    await screen.findByRole('status')
    expect(onChanged).toHaveBeenCalledTimes(1)

    mockApi(() => json(null, 204))
    await user.click(screen.getByRole('button', { name: 'Quitar' }))
    await screen.findByText(/Todavía no cargaste la cifra/)
    expect(onChanged).toHaveBeenCalledTimes(2)
  })
})
