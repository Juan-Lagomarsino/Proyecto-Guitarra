import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { defaultTheme, type ThemeTokens } from '../../theme/defaultTheme'
import { ThemeProvider } from '../../theme/ThemeProvider'
import { getSettings, toTheme } from './settingsApi'

interface SavedThemeValue {
  /** Tema aplicado hoy a toda la app. */
  theme: ThemeTokens
  applyTheme: (theme: ThemeTokens) => void
}

const SavedThemeContext = createContext<SavedThemeValue>({
  theme: defaultTheme,
  applyTheme: () => {},
})

export const useSavedTheme = () => useContext(SavedThemeContext)

/** Aplica el tema por defecto y, apenas llega GET /settings, el guardado. */
export function SavedThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeTokens>(defaultTheme)

  useEffect(() => {
    const controller = new AbortController()
    getSettings(controller.signal)
      .then((settings) => setTheme({ ...defaultTheme, ...toTheme(settings) }))
      .catch(() => {
        // sin API o sin ajustes: queda el tema por defecto
      })
    return () => controller.abort()
  }, [])

  const applyTheme = useCallback((next: ThemeTokens) => setTheme(next), [])
  const value = useMemo(() => ({ theme, applyTheme }), [theme, applyTheme])

  return (
    <SavedThemeContext.Provider value={value}>
      <ThemeProvider theme={theme}>{children}</ThemeProvider>
    </SavedThemeContext.Provider>
  )
}
