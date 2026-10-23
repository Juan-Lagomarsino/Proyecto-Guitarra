import { useCallback } from 'react'
import Markdown from 'react-markdown'
import { Link, useParams } from 'react-router-dom'
import { AsyncView } from './AsyncView'
import { ExerciseCard } from './ExerciseCard'
import { fetchLesson, fetchLessons, fetchLevels } from './studyApi'
import { useAsyncData } from './useAsyncData'
import './StudyViews.css'

function useIdParam(name: string): number {
  return Number(useParams()[name])
}

/** Lista de niveles. La API de /levels aún no trae avance; ver GET /progress/summary (T11). */
export function LevelsView() {
  const state = useAsyncData(fetchLevels)
  return (
    <section className="page study">
      <h2 className="display page-title">Estudio</h2>
      <AsyncView state={state}>
        {(levels) => (
          <ol className="study-list">
            {levels.map((level) => (
              <li key={level.id}>
                <Link
                  className="study-item"
                  to={`/estudio/niveles/${level.id}`}
                >
                  <span className="study-item__num display">
                    {level.position}
                  </span>
                  <span className="study-item__body">
                    <span className="study-item__title">{level.name}</span>
                    <span className="study-item__desc">
                      {level.description}
                    </span>
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </AsyncView>
    </section>
  )
}

export function LevelView() {
  const levelId = useIdParam('levelId')
  const loadLessons = useCallback(
    (signal: AbortSignal) => fetchLessons(levelId, signal),
    [levelId],
  )
  const lessons = useAsyncData(loadLessons)
  const levels = useAsyncData(fetchLevels)
  const levelName =
    levels.status === 'ready'
      ? levels.data.find((level) => level.id === levelId)?.name
      : undefined

  return (
    <section className="page study">
      <Link className="study-back" to="/estudio">
        ← Niveles
      </Link>
      <h2 className="display page-title">{levelName ?? 'Nivel'}</h2>
      <AsyncView state={lessons}>
        {(items) =>
          items.length === 0 ? (
            <p className="study-status">
              Este nivel todavía no tiene lecciones.
            </p>
          ) : (
            <ol className="study-list">
              {items.map((lesson) => (
                <li key={lesson.id}>
                  <Link
                    className="study-item"
                    to={`/estudio/lecciones/${lesson.id}`}
                  >
                    <span className="study-item__num display">
                      {lesson.position}
                    </span>
                    <span className="study-item__body">
                      <span className="study-item__title">{lesson.title}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )
        }
      </AsyncView>
    </section>
  )
}

export function LessonView() {
  const lessonId = useIdParam('lessonId')
  const load = useCallback(
    (signal: AbortSignal) => fetchLesson(lessonId, signal),
    [lessonId],
  )
  const state = useAsyncData(load)

  return (
    <section className="page study">
      <AsyncView state={state}>
        {(lesson) => (
          <>
            <Link
              className="study-back"
              to={`/estudio/niveles/${lesson.level_id}`}
            >
              ← Lecciones
            </Link>
            <h2 className="display page-title">{lesson.title}</h2>
            <div className="study-theory">
              <Markdown>{lesson.content_md}</Markdown>
            </div>
            <div className="study-cards">
              {lesson.exercises.map((exercise) => (
                <ExerciseCard key={exercise.id} exercise={exercise} />
              ))}
            </div>
          </>
        )}
      </AsyncView>
    </section>
  )
}
