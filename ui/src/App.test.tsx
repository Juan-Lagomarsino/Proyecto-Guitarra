import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('muestra el título de la app', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: /práctica de guitarra/i }),
    ).toBeInTheDocument()
  })
})
