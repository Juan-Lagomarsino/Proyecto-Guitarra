import { render } from '@testing-library/react'
import { ThemeProvider } from './ThemeProvider'
import { defaultTheme } from './defaultTheme'

describe('ThemeProvider', () => {
  it('escribe cada token como variable CSS en el elemento raíz', () => {
    render(
      <ThemeProvider theme={{ '--bg': 'rgb(1, 2, 3)', '--accent': 'red' }}>
        x
      </ThemeProvider>,
    )

    const style = document.documentElement.style
    expect(style.getPropertyValue('--bg')).toBe('rgb(1, 2, 3)')
    expect(style.getPropertyValue('--accent')).toBe('red')
  })

  it('usa el tema por defecto si no recibe uno', () => {
    render(<ThemeProvider>x</ThemeProvider>)

    for (const [name, value] of Object.entries(defaultTheme)) {
      expect(document.documentElement.style.getPropertyValue(name)).toBe(value)
    }
  })

  it('el tema por defecto define los tokens semánticos del plan', () => {
    const required = [
      '--bg',
      '--surface',
      '--surface-2',
      '--line',
      '--text',
      '--muted',
      '--accent',
      '--accent-dim',
      '--accent-ink',
      '--good',
      '--good-dim',
      '--warn',
      '--note-tonic',
      '--note-other',
      '--note-active',
      '--string',
      '--fret',
      '--wood',
      '--font-display',
      '--font-mono',
    ]
    for (const token of required)
      expect(Object.keys(defaultTheme)).toContain(token)
  })
})
