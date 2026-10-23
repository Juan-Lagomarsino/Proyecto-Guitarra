import { AppRoutes } from './app/AppRoutes'
import { SavedThemeProvider } from './features/settings/SavedTheme'

/** Debe renderizarse dentro de un Router (lo pone main.tsx). */
export default function App() {
  return (
    <SavedThemeProvider>
      <AppRoutes />
    </SavedThemeProvider>
  )
}
