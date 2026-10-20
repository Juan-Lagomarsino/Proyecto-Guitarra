import { NavLink, Outlet } from 'react-router-dom'

const ENABLED_ITEMS = [
  { to: '/', label: 'Hoy', end: true },
  { to: '/estudio', label: 'Estudio', end: false },
  { to: '/progreso', label: 'Progreso', end: false },
  { to: '/ajustes', label: 'Ajustes', end: false },
]

const DISABLED_ITEMS = ['Explorar', 'Rig']

export function AppShell() {
  return (
    <div className="wrap">
      <header className="top">
        <div>
          <div className="brand">Taller de práctica</div>
          <h1 className="display">
            Guitarra <em>eléctrica</em>
          </h1>
        </div>
      </header>

      <nav className="tabs" aria-label="Principal">
        {ENABLED_ITEMS.map(({ to, label, end }) => (
          <NavLink key={to} to={to} end={end} className="tab">
            {label}
          </NavLink>
        ))}
        {DISABLED_ITEMS.map((label) => (
          <span
            key={label}
            className="tab"
            aria-disabled="true"
            title="Próximamente"
          >
            {label}
          </span>
        ))}
      </nav>

      <main>
        <Outlet />
      </main>
    </div>
  )
}
