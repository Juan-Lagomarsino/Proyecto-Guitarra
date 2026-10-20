interface PlaceholderPageProps {
  title: string
  description: string
}

function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <section className="page">
      <h2 className="display page-title">{title}</h2>
      <p className="page-note">{description}</p>
    </section>
  )
}

export const TodayPage = () => (
  <PlaceholderPage
    title="Sesión de hoy"
    description="Acá va a ir la sesión armada para hoy."
  />
)

export const StudyPage = () => (
  <PlaceholderPage
    title="Estudio"
    description="Acá van a ir los niveles y ejercicios."
  />
)

export const ProgressPage = () => (
  <PlaceholderPage
    title="Progreso"
    description="Acá van a ir la racha y tu avance."
  />
)

export const SettingsPage = () => (
  <PlaceholderPage
    title="Ajustes"
    description="Acá van a ir la zona horaria y los recordatorios."
  />
)
