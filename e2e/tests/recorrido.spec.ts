import { expect, test, type Locator, type Page } from '@playwright/test'
import path from 'node:path'

// Recorrido ordenado sobre una base vacía: cada test depende del estado que dejó el anterior.
test.describe.configure({ mode: 'serial' })

// Misma zona que usa la API por defecto, para que "hoy" coincida entre navegador y servidor.
test.use({ timezoneId: 'America/Montevideo' })

const CAPTURAS = path.resolve(
  import.meta.dirname,
  '../../docs/fases/fase-1/capturas',
)

const capturar = (page: Page, nombre: string) =>
  page.screenshot({ path: path.join(CAPTURAS, `${nombre}.png`) })

const primeraTarjeta = (page: Page) => page.locator('.exercise-card').first()

/** Posición horizontal de la nota activa en la tab (cambia cuando avanza la nota). */
async function notaActivaEnTab(tarjeta: Locator): Promise<number> {
  const activa = tarjeta.locator('[data-role="note"][data-active="true"]')
  await expect(activa).toHaveCount(1)
  const box = await activa.boundingBox()
  return box!.x
}

/** Traste y cuerda de la nota activa en el mástil. */
async function notaActivaEnMastil(tarjeta: Locator): Promise<string> {
  const activa = tarjeta.locator('[data-testid="note"][data-state="active"]')
  await expect(activa).toHaveCount(1)
  return `${await activa.getAttribute('data-string')}:${await activa.getAttribute('data-fret')}`
}

function hoyDdMmAaaa(): string {
  const partes = new Intl.DateTimeFormat('es-UY', {
    timeZone: 'America/Montevideo',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).formatToParts(new Date())
  const valor = (tipo: string) => partes.find((p) => p.type === tipo)!.value
  return `${valor('day')}/${valor('month')}/${valor('year')}`
}

test('1. la sesión del día muestra bloques con ejercicios', async ({
  page,
}) => {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Sesión de hoy' }),
  ).toBeVisible()
  await expect(page.locator('.session-block').first()).toBeVisible()
  await expect(page.locator('.session-block__title').first()).toContainText(
    'min',
  )
  await expect(primeraTarjeta(page)).toBeVisible()
  await expect(page.locator('.session-summary')).toContainText(/^0 de \d+ hechos/)
  await capturar(page, 'sesion-del-dia')
})

test('2 y 3. reproducir avanza la nota; nota por nota con siguiente y anterior', async ({
  page,
}) => {
  await page.goto('/')
  const tarjeta = primeraTarjeta(page)
  await expect(tarjeta).toBeVisible()

  await tarjeta.getByRole('button', { name: 'Reproducir' }).click()
  await expect(tarjeta.getByRole('button', { name: 'Pausar' })).toBeVisible()

  // Con la reproducción en curso, la nota activa tiene que cambiar en la tab y en el mástil.
  const tabVistas = new Set<number>()
  const mastilVistas = new Set<string>()
  await expect
    .poll(
      async () => {
        const activaTab = tarjeta.locator(
          '[data-role="note"][data-active="true"]',
        )
        const activaMastil = tarjeta.locator(
          '[data-testid="note"][data-state="active"]',
        )
        if ((await activaTab.count()) === 1) {
          tabVistas.add((await activaTab.boundingBox())!.x)
        }
        if ((await activaMastil.count()) === 1) {
          mastilVistas.add(
            `${await activaMastil.getAttribute('data-string')}:${await activaMastil.getAttribute('data-fret')}`,
          )
        }
        return tabVistas.size
      },
      { timeout: 20_000, intervals: [100] },
    )
    .toBeGreaterThanOrEqual(2)
  expect(mastilVistas.size).toBeGreaterThanOrEqual(1)
  await tarjeta.screenshot({
    path: path.join(CAPTURAS, 'tarjeta-reproduciendo.png'),
  })

  await tarjeta.getByRole('button', { name: 'Pausar' }).click()
  await expect(tarjeta.getByRole('button', { name: 'Reproducir' })).toBeVisible()

  // Nota por nota.
  await tarjeta.getByRole('button', { name: 'Nota por nota' }).click()
  const siguiente = tarjeta.getByRole('button', { name: /Siguiente/ })
  const anterior = tarjeta.getByRole('button', { name: /Anterior/ })
  await expect(siguiente).toBeEnabled()

  const antes = await notaActivaEnTab(tarjeta)
  await siguiente.click()
  await expect.poll(() => notaActivaEnTab(tarjeta)).toBeGreaterThan(antes)
  const mastilDespues = await notaActivaEnMastil(tarjeta)
  expect(mastilDespues).toMatch(/^\d:\d+$/)

  await anterior.click()
  await expect.poll(() => notaActivaEnTab(tarjeta)).toBe(antes)
})

test('4. Terminé marca el ejercicio como hecho hoy', async ({ page }) => {
  await page.goto('/')
  const tarjeta = primeraTarjeta(page)
  await expect(tarjeta).toBeVisible()
  await tarjeta.getByRole('button', { name: 'Terminé' }).click()
  await expect(page.getByText('✓ Hecho hoy')).toHaveCount(1)
  await expect(page.locator('.session-summary')).toContainText(/^1 de \d+ hechos/)

  // Persiste: tras recargar sigue como hecho hoy.
  await page.reload()
  await expect(page.getByText('✓ Hecho hoy')).toHaveCount(1)
})

test('5. Progreso muestra racha 1 y el día de hoy marcado', async ({ page }) => {
  await page.goto('/progreso')
  await expect(page.getByRole('heading', { name: 'Progreso' })).toBeVisible()
  const racha = page
    .locator('.progress-stat')
    .filter({ hasText: 'Racha actual' })
  await expect(racha).toContainText('1 día')

  const hoy = page.getByRole('img', { name: `${hoyDdMmAaaa()}: 1 ejercicio` })
  await expect(hoy).toBeVisible()
  await expect(hoy).not.toHaveAttribute('data-level', '0')
  await capturar(page, 'progreso-despues-de-termine')
})

test('6. un color del tema cambiado en Ajustes persiste tras recargar', async ({
  page,
}) => {
  const nuevoColor = '#12ab34'
  await page.goto('/ajustes')
  const campo = page.locator('#color---accent')
  await expect(campo).toBeVisible()
  await campo.fill(nuevoColor)
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Ajustes guardados.')).toBeVisible()
  await capturar(page, 'ajustes-color-cambiado')

  await page.reload()
  await expect(
    page.getByRole('heading', { name: 'Ajustes' }),
  ).toBeVisible()
  await expect
    .poll(() =>
      page.evaluate(() =>
        document.documentElement.style.getPropertyValue('--accent').trim(),
      ),
    )
    .toBe(nuevoColor)
  await expect(page.locator('#color---accent')).toHaveValue(nuevoColor)
})

test('7. sin scroll horizontal de página a 375 px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 })
  const pantallas = [
    { ruta: '/', listo: '.exercise-card' },
    { ruta: '/estudio', listo: '.study-list' },
    { ruta: '/progreso', listo: '.heatmap' },
    { ruta: '/ajustes', listo: '.settings-form' },
  ]
  for (const { ruta, listo } of pantallas) {
    await page.goto(ruta)
    await expect(page.locator(listo).first()).toBeVisible()
    const ancho = await page.evaluate(
      () => document.documentElement.scrollWidth,
    )
    expect(ancho, `scrollWidth en ${ruta}`).toBeLessThanOrEqual(375)
    if (ruta === '/') await capturar(page, 'vista-375px')
  }
})

test('8. Estudio: nivel, lección y tarjeta con teoría y descripción', async ({
  page,
}) => {
  await page.goto('/estudio')
  await expect(page.getByRole('heading', { name: 'Estudio' })).toBeVisible()
  await page.locator('a.study-item').first().click()

  await expect(page.getByRole('link', { name: '← Niveles' })).toBeVisible()
  await page.locator('a.study-item').first().click()

  await expect(page.getByRole('link', { name: '← Lecciones' })).toBeVisible()
  // La teoría llega como markdown ya renderizado (párrafos, listas o títulos), no como texto crudo.
  const teoria = page.locator('.study-theory')
  await expect(teoria.locator('p, ul, ol, h1, h2, h3').first()).toBeVisible()
  await expect(teoria).not.toContainText('**')

  const tarjeta = primeraTarjeta(page)
  await expect(tarjeta).toBeVisible()
  await expect(tarjeta.locator('.exercise-card__description')).not.toBeEmpty()
  await expect(tarjeta.getByRole('button', { name: 'Reproducir' })).toBeVisible()
})
