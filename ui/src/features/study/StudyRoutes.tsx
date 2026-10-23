import { Route, Routes } from 'react-router-dom'
import { LessonView, LevelsView, LevelView } from './StudyViews'

/** Rutas anidadas bajo /estudio/*. */
export function StudyRoutes() {
  return (
    <Routes>
      <Route index element={<LevelsView />} />
      <Route path="niveles/:levelId" element={<LevelView />} />
      <Route path="lecciones/:lessonId" element={<LessonView />} />
    </Routes>
  )
}
