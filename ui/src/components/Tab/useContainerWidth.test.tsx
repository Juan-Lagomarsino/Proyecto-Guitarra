import { act, render, screen } from '@testing-library/react'
import { useContainerWidth } from './useContainerWidth'

function Probe({ width }: { width?: number }) {
  const [ref, measured] = useContainerWidth<HTMLDivElement>(width)
  return (
    <div ref={ref} data-testid="probe">
      {measured}
    </div>
  )
}

describe('useContainerWidth', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('devuelve el ancho fijo sin observar', () => {
    const observe = vi.fn()
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe = observe
        disconnect() {}
      },
    )
    render(<Probe width={300} />)
    expect(screen.getByTestId('probe')).toHaveTextContent('300')
    expect(observe).not.toHaveBeenCalled()
  })

  it('mide el contenedor y reacciona a los cambios de tamaño', () => {
    let callback: ResizeObserverCallback = () => {}
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(cb: ResizeObserverCallback) {
          callback = cb
        }
        observe() {}
        disconnect() {}
      },
    )
    render(<Probe />)
    expect(screen.getByTestId('probe')).toHaveTextContent('0')
    act(() => {
      callback(
        [{ contentRect: { width: 420 } } as ResizeObserverEntry],
        {} as ResizeObserver,
      )
    })
    expect(screen.getByTestId('probe')).toHaveTextContent('420')
  })

  it('no rompe sin ResizeObserver', () => {
    vi.stubGlobal('ResizeObserver', undefined)
    render(<Probe />)
    expect(screen.getByTestId('probe')).toHaveTextContent('0')
  })
})
