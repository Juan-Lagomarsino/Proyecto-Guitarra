import { Link } from 'react-router-dom'

/** Provisorio hasta F2-T16 (vista de canción). */
export function SongPlaceholder() {
  return (
    <section className="page">
      <h2 className="display page-title">Canción</h2>
      <p className="page-note">La vista de la canción llega pronto.</p>
      <Link to="/explorar" className="study-back">
        ← Volver a Explorar
      </Link>
    </section>
  )
}
