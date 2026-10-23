import { Route, Routes } from 'react-router-dom'
import { TodayPage } from '../pages/Pages'
import { ProgressScreen } from '../features/progress/ProgressScreen'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { StudyRoutes } from '../features/study/StudyRoutes'
import { AppShell } from './AppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<TodayPage />} />
        <Route path="estudio/*" element={<StudyRoutes />} />
        <Route path="progreso" element={<ProgressScreen />} />
        <Route path="ajustes" element={<SettingsScreen />} />
      </Route>
    </Routes>
  )
}
