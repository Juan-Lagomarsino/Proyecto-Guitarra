import { useState, type FormEvent } from 'react'
import { deleteCifra, saveCifra } from '../../api/songs'
import { errorText } from '../explore/analysis'

interface CifraPanelProps {
  songId: number
  hasCifra: boolean
  cifraUrl: string | null
  /** Avisa que la cifra cambió, para que la vista recargue el detalle. */
  onChanged?: () => void
}

function hostOf(url: string): string {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}

/** Cifra de Cifra Club pegada a mano (ADR 0012): al guardarla se reanaliza la canción. */
export function CifraPanel(props: CifraPanelProps) {
  const [hasCifra, setHasCifra] = useState(props.hasCifra)
  const [cifraUrl, setCifraUrl] = useState(props.cifraUrl)
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const open = () => {
    setUrl(cifraUrl ?? '')
    setText('')
    setProblem(null)
    setNotice(null)
    setEditing(true)
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const link = url.trim() || null
    setBusy(true)
    setProblem(null)
    try {
      const saved = await saveCifra(props.songId, { text, url: link })
      setHasCifra(true)
      setCifraUrl(link)
      setEditing(false)
      props.onChanged?.()
      setNotice(
        saved.reanalysis_queued
          ? 'Cifra guardada. Se está reanalizando la canción con esos acordes.'
          : 'Cifra guardada. Había un análisis en curso: la usás en el próximo reanálisis.',
      )
    } catch (error) {
      setProblem(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    setProblem(null)
    setNotice(null)
    try {
      await deleteCifra(props.songId)
      setHasCifra(false)
      setCifraUrl(null)
      props.onChanged?.()
    } catch (error) {
      setProblem(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="cifra" aria-labelledby="cifra-title">
      <h3 id="cifra-title" className="progress-subtitle">
        Cifra de Cifra Club
      </h3>
      <p className="cifra__state">
        {hasCifra ? 'Cifra cargada.' : 'Todavía no cargaste la cifra.'}{' '}
        {cifraUrl && (
          <a href={cifraUrl} target="_blank" rel="noreferrer">
            {hostOf(cifraUrl)}
          </a>
        )}
      </p>
      <p className="page-note">
        Copiá el texto de la cifra desde la página de Cifra Club y pegalo acá.
      </p>
      {!editing && (
        <div className="cifra__actions">
          <button type="button" className="cifra__button" onClick={open}>
            {hasCifra ? 'Reemplazar cifra' : 'Cargar cifra'}
          </button>
          {hasCifra && (
            <button
              type="button"
              className="cifra__button"
              disabled={busy}
              onClick={() => void remove()}
            >
              Quitar
            </button>
          )}
        </div>
      )}
      {editing && (
        <form className="cifra__form" onSubmit={(e) => void submit(e)}>
          <label className="cifra__field">
            Texto de la cifra
            <textarea
              value={text}
              rows={10}
              maxLength={50000}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <label className="cifra__field">
            Link de la cifra (opcional)
            <input
              type="url"
              inputMode="url"
              value={url}
              placeholder="https://www.cifraclub.com.br/…"
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <div className="cifra__actions">
            <button
              type="submit"
              className="cifra__button cifra__button--primary"
              disabled={busy || text.trim() === ''}
            >
              Guardar
            </button>
            <button
              type="button"
              className="cifra__button"
              disabled={busy}
              onClick={() => setEditing(false)}
            >
              Cancelar
            </button>
          </div>
        </form>
      )}
      {notice && (
        <p role="status" className="cifra__notice">
          {notice}
        </p>
      )}
      {problem && (
        <p role="alert" className="cifra__problem">
          {problem}
        </p>
      )}
    </section>
  )
}
