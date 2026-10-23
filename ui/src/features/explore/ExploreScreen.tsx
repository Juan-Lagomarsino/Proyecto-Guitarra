import { useState } from 'react'
import type { CreatedSong } from '../../api/songs'
import { AddSongForm } from './AddSongForm'
import { SongRow } from './SongRow'
import { useSongLibrary } from './useSongLibrary'
import './explore.css'

export function ExploreScreen() {
  const { state, reload } = useSongLibrary()
  const [highlightedId, setHighlightedId] = useState<number | null>(null)
  const [existed, setExisted] = useState(false)

  const handleCreated = ({ existed: already, song }: CreatedSong) => {
    setHighlightedId(song.id)
    setExisted(already)
    void reload()
  }

  return (
    <section className="page explore">
      <h2 className="display page-title">Explorar</h2>
      <p className="page-note">
        Sumá una canción y la analizamos para que puedas tocarla.
      </p>
      <AddSongForm onCreated={handleCreated} />
      {existed && (
        <p role="status" className="explore-notice">
          Ya la tenías
        </p>
      )}

      <h3 className="progress-subtitle">Tu biblioteca</h3>
      {state.status === 'loading' && <p className="page-note">Cargando…</p>}
      {state.status === 'error' && (
        <p role="alert" className="page-note">
          No se pudo cargar la biblioteca: {state.message}
        </p>
      )}
      {state.status === 'ready' && state.songs.length === 0 && (
        <p className="page-note">
          Todavía no tenés canciones. Pegá un link de YouTube o Spotify, o buscá
          una por título y artista, y aparece acá mientras se analiza.
        </p>
      )}
      {state.status === 'ready' && state.songs.length > 0 && (
        <ul className="explore-list">
          {state.songs.map((song) => (
            <SongRow
              key={song.id}
              song={song}
              highlighted={song.id === highlightedId}
              onReanalyzed={() => void reload()}
            />
          ))}
        </ul>
      )}
    </section>
  )
}
