import { Route, Routes } from 'react-router-dom'
import { ExploreScreen } from '../features/explore/ExploreScreen'
import { SongScreen } from '../features/song/SongScreen'
import { TodayScreen } from '../features/session/TodayScreen'
import { ProgressScreen } from '../features/progress/ProgressScreen'
import { SettingsScreen } from '../features/settings/SettingsScreen'
import { StudyRoutes } from '../features/study/StudyRoutes'
import { AppShell } from './AppShell'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<TodayScreen />} />
        <Route path="estudio/*" element={<StudyRoutes />} />
        <Route path="explorar" element={<ExploreScreen />} />
        <Route path="explorar/canciones/:id" element={<SongScreen />} />
        <Route path="progreso" element={<ProgressScreen />} />
        <Route path="ajustes" element={<SettingsScreen />} />
      </Route>
    </Routes>
  )
}
