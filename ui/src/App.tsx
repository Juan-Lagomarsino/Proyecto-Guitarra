import { AppRoutes } from './app/AppRoutes'
import { ThemeProvider } from './theme/ThemeProvider'

/** Debe renderizarse dentro de un Router (lo pone main.tsx). */
export default function App() {
  return (
    <ThemeProvider>
      <AppRoutes />
    </ThemeProvider>
  )
}
