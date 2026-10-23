import { useState, type FormEvent } from 'react'
import { createSong, type CreatedSong, type NewSong } from '../../api/songs'
import { errorText, looksLikeSongLink } from './analysis'

type Mode = 'link' | 'name'

interface AddSongFormProps {
  onCreated: (result: CreatedSong) => void
}

const MODES: { mode: Mode; label: string }[] = [
  { mode: 'link', label: 'Pegar link' },
  { mode: 'name', label: 'Buscar por nombre' },
]

/** Devuelve el cuerpo a enviar, o el mensaje de validación liviana. */
function buildRequest(
  mode: Mode,
  link: string,
  title: string,
  artist: string,
): { body: NewSong } | { problem: string } {
  if (mode === 'link') {
    if (!looksLikeSongLink(link))
      return { problem: 'Eso no parece un link de YouTube o Spotify.' }
    return { body: { url: link.trim() } }
  }
  if (!title.trim() || !artist.trim())
    return { problem: 'Completá el título y el artista.' }
  return { body: { title: title.trim(), artist: artist.trim() } }
}

export function AddSongForm({ onCreated }: AddSongFormProps) {
  const [mode, setMode] = useState<Mode>('link')
  const [link, setLink] = useState('')
  const [title, setTitle] = useState('')
  const [artist, setArtist] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const request = buildRequest(mode, link, title, artist)
    if ('problem' in request) {
      setProblem(request.problem)
      return
    }
    setProblem(null)
    setSending(true)
    try {
      onCreated(await createSong(request.body))
      setLink('')
      setTitle('')
      setArtist('')
    } catch (error) {
      setProblem(errorText(error))
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="explore-form" onSubmit={(e) => void submit(e)} noValidate>
      <div className="explore-modes">
        {MODES.map((item) => (
          <button
            key={item.mode}
            type="button"
            className="explore-mode"
            aria-pressed={mode === item.mode}
            onClick={() => {
              setMode(item.mode)
              setProblem(null)
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {mode === 'link' ? (
        <label className="explore-field">
          <span>Link de YouTube o Spotify</span>
          <input
            type="text"
            inputMode="url"
            value={link}
            placeholder="https://www.youtube.com/watch?v=…"
            onChange={(e) => setLink(e.target.value)}
          />
        </label>
      ) : (
        <div className="explore-fields">
          <label className="explore-field">
            <span>Título</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <label className="explore-field">
            <span>Artista</span>
            <input
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
            />
          </label>
        </div>
      )}

      {problem && (
        <p role="alert" className="explore-problem">
          {problem}
        </p>
      )}
      <button type="submit" className="explore-submit" disabled={sending}>
        {sending ? 'Agregando…' : 'Agregar'}
      </button>
    </form>
  )
}
