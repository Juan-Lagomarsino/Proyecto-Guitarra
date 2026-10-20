import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

describe('App', () => {
  it('muestra la marca y aplica el tema', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /guitarra/i,
    )
    expect(document.documentElement.style.getPropertyValue('--bg')).not.toBe('')
  })
})
