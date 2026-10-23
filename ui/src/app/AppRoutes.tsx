import { Route, Routes } from 'react-router-dom'
import { ProgressPage, TodayPage } from '../pages/Pages'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { StudyRoutes } from '../features/study/StudyRoutes'
import { AppShell } from './AppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<TodayPage />} />
        <Route path="estudio/*" element={<StudyRoutes />} />
        <Route path="progreso" element={<ProgressPage />} />
        <Route path="ajustes" element={<SettingsScreen />} />
      </Route>
    </Routes>
  )
}
