import { useState, type ReactNode } from 'react'
import type { SongChartResponse } from '../../api/songs'
import type { ChartSection } from '../../songs/types'
import { RiffEditor } from './RiffEditor'
import { RevertButton } from './SectionEditing'
import './chartEdit.css'
import './riffEditor.css'

interface RiffEditingProps {
  songId: number
  chart: SongChartResponse
  section: ChartSection
  onChange: (chart: SongChartResponse) => void
  /** La vista normal del riff (tab y mástil), o nada si la sección no tiene. */
  children: ReactNode
}

/** Barra "Editar tab" / "Agregar riff" del bloque Riff; mientras se edita reemplaza a la vista. */
export function RiffEditing({
  songId,
  chart,
  section,
  onChange,
  children,
}: RiffEditingProps) {
  const [editing, setEditing] = useState(false)
  const byUser = chart.riff_sources?.[section.id] === 'usuario'

  if (editing) {
    return (
      <RiffEditor
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
    )
  }
  return (
    <>
      {children}
      <div className="riff-edit__bar">
        {byUser && <span className="song-badge">Riff editado por vos</span>}
        <button
          type="button"
          className="chart-edit__button"
          onClick={() => setEditing(true)}
        >
          {section.riff ? 'Editar tab' : 'Agregar riff'}
        </button>
        {byUser && (
          <RevertButton songId={songId} chart={chart} onChange={onChange} />
        )}
      </div>
    </>
  )
}
