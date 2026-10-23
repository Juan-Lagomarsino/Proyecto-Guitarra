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
