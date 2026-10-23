import { Route, Routes } from 'react-router-dom'
import { ProgressPage, StudyPage, TodayPage } from '../pages/Pages'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { AppShell } from './AppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<TodayPage />} />
        <Route path="estudio" element={<StudyPage />} />
        <Route path="progreso" element={<ProgressPage />} />
        <Route path="ajustes" element={<SettingsScreen />} />
      </Route>
    </Routes>
  )
}
