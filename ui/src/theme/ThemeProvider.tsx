import { useLayoutEffect, type ReactNode } from 'react'
import { defaultTheme, type ThemeTokens } from './defaultTheme'

interface ThemeProviderProps {
  theme?: ThemeTokens
  children: ReactNode
}

/** Escribe los tokens del tema como variables CSS en <html>. */
export function ThemeProvider({
  theme = defaultTheme,
  children,
}: ThemeProviderProps) {
  useLayoutEffect(() => {
    const style = document.documentElement.style
    for (const [name, value] of Object.entries(theme))
      style.setProperty(name, value)
    return () => {
      for (const name of Object.keys(theme)) style.removeProperty(name)
    }
  }, [theme])

  return <>{children}</>
}
