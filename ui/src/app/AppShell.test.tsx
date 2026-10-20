import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './AppRoutes'

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )

describe('AppShell', () => {
  it('muestra la sesión de hoy en /', () => {
    renderAt('/')
    expect(
      screen.getByRole('heading', { level: 2, name: /sesión de hoy/i }),
    ).toBeInTheDocument()
  })

  it.each([
    ['/estudio', /estudio/i],
    ['/progreso', /progreso/i],
    ['/ajustes', /ajustes/i],
  ])('muestra la página de %s', (path, name) => {
    renderAt(path)
    expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument()
  })

  it('la navegación tiene Hoy, Estudio, Progreso y Ajustes como enlaces', () => {
    renderAt('/')
    const nav = screen.getByRole('navigation', { name: /principal/i })
    for (const name of ['Hoy', 'Estudio', 'Progreso', 'Ajustes']) {
      expect(nav).toContainElement(screen.getByRole('link', { name }))
    }
  })

  it('Explorar y Rig están deshabilitadas y no son enlaces', () => {
    renderAt('/')
    expect(screen.queryByRole('link', { name: 'Explorar' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Rig' })).toBeNull()
    expect(screen.getByText('Explorar')).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    expect(screen.getByText('Rig')).toHaveAttribute('aria-disabled', 'true')
  })

  it('navega al hacer clic en un enlace', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'Progreso' }))
    expect(
      screen.getByRole('heading', { level: 2, name: /progreso/i }),
    ).toBeInTheDocument()
  })
})
