import { useState, type ReactNode } from 'react'
import { discardUserChart, type SongChartResponse } from '../../api/songs'
import type { ChartSection } from '../../songs/types'
import { SectionEditor } from './SectionEditor'
import './chartEdit.css'

interface SectionEditingProps {
  songId: number
  chart: SongChartResponse
  section: ChartSection
  onChange: (chart: SongChartResponse) => void
  /** La vista normal de la sección, que se muestra cuando no se está editando. */
  children: ReactNode
}

export function RevertButton({
  songId,
  chart,
  onChange,
}: Pick<SectionEditingProps, 'songId' | 'chart' | 'onChange'>) {
  const [asking, setAsking] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function revert() {
    try {
      onChange(await discardUserChart(songId, chart.instrument))
    } catch (error) {
      setProblem(error instanceof Error ? error.message : 'Error desconocido')
      setAsking(false)
    }
  }

  return (
    <>
      {asking ? (
        <span
          className="chart-edit__confirm"
          role="group"
          aria-label="Confirmar"
        >
          ¿Descartar tus cambios?
          <button
            type="button"
            className="chart-edit__button"
            onClick={() => void revert()}
          >
            Sí, volver
          </button>
          <button
            type="button"
            className="chart-edit__button"
            onClick={() => setAsking(false)}
          >
            No
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="chart-edit__button"
          onClick={() => setAsking(true)}
        >
          Volver a la automática
        </button>
      )}
      {problem && (
        <p role="alert" className="chart-edit__problem">
          {problem}
        </p>
      )}
    </>
  )
}

/** Barra de edición en el lugar; mientras se edita reemplaza a la vista de la sección. */
export function SectionEditing({
  songId,
  chart,
  section,
  onChange,
  children,
}: SectionEditingProps) {
  const [editing, setEditing] = useState(false)
  const edited = chart.origin === 'user'

  return (
    <div className="chart-edit">
      <div className="chart-edit__bar">
        {edited && <span className="song-badge">Editado por vos</span>}
        {!editing && (
          <button
            type="button"
            className="chart-edit__button"
            onClick={() => setEditing(true)}
          >
            Editar sección
          </button>
        )}
        {edited && !editing && (
          <RevertButton songId={songId} chart={chart} onChange={onChange} />
        )}
      </div>
      {editing ? (
        <SectionEditor
          key={section.id}
          songId={songId}
          content={chart.content}
          section={section}
          onCancel={() => setEditing(false)}
          onSaved={(saved) => {
            setEditing(false)
            onChange(saved)
          }}
        />
      ) : (
        children
      )}
    </div>
  )
}
