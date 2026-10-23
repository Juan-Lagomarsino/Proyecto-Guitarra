import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

// Recorrido de canciones: va después de recorrido.spec.ts (orden alfabético) sobre la misma base.
// El worker real no participa: se lo simula contra la API con un resultado grabado.
test.describe.configure({ mode: 'serial' })
test.use({ timezoneId: 'America/Montevideo' })

const CAPTURAS = path.resolve(
  import.meta.dirname,
  '../../docs/fases/fase-2/capturas',
)
const RESULTADO = JSON.parse(
  fs.readFileSync(
    path.resolve(import.meta.dirname, '../fixtures/resultado-grabado.json'),
    'utf-8',
  ),
)
const TOKEN_UI = process.env.E2E_API_TOKEN ?? 'e2e-token-de-prueba'
const TOKEN_WORKER =
  process.env.E2E_WORKER_TOKEN ?? 'e2e-worker-token-de-prueba'
const LINK = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
const TITULO = RESULTADO.metadata.title as string

const capturar = (page: Page, nombre: string) =>
  page.screenshot({ path: path.join(CAPTURAS, `${nombre}.png`) })

// El worker usa su propio token, que solo sirve en /jobs.
const headersWorker = { Authorization: `Bearer ${TOKEN_WORKER}` }

test.beforeAll(() => {
  fs.mkdirSync(CAPTURAS, { recursive: true })
})

async function abrirCancion(page: Page) {
  await page.goto('/explorar')
  await page.getByRole('link', { name: TITULO }).click()
  await expect(page.getByRole('heading', { name: TITULO })).toBeVisible()
}

test('1. pegar un link de YouTube en Explorar encola el análisis', async ({
  page,
}) => {
  await page.goto('/explorar')
  await page.getByLabel('Link de YouTube o Spotify').fill(LINK)
  await page.getByRole('button', { name: 'Agregar' }).click()
  await expect(page.locator('.explore-song')).toHaveCount(1)
  await expect(page.locator('.explore-chip')).toHaveText('En cola')
})

test('2. el worker (simulado) toma el trabajo y entrega el resultado grabado', async ({
  request,
  page,
}) => {
  const conTokenDeUi = await request.post('/api/v1/jobs/claim', {
    data: { worker_id: 'e2e' },
    headers: { Authorization: `Bearer ${TOKEN_UI}` },
  })
  expect(conTokenDeUi.status(), 'el token de la UI no sirve en /jobs').toBe(401)

  const claim = await request.post('/api/v1/jobs/claim', {
    data: { worker_id: 'e2e' },
    headers: headersWorker,
  })
  expect(claim.status()).toBe(200)
  const job = await claim.json()

  const result = await request.post(`/api/v1/jobs/${job.job_id}/result`, {
    data: { worker_id: 'e2e', ...RESULTADO },
    headers: headersWorker,
  })
  expect(result.status(), await result.text()).toBe(200)

  await page.goto('/explorar')
  await expect(page.locator('.explore-chip')).toHaveText('Lista')
})

test('3. la canción lista muestra secciones, acordes con diagrama y clásica/eléctrica', async ({
  page,
}) => {
  await abrirCancion(page)

  for (const nombre of ['Intro', 'Estrofa', 'Estribillo']) {
    await expect(
      page.getByRole('button', { name: new RegExp(nombre) }).first(),
    ).toBeVisible()
  }
  const progresion = page.getByRole('list', { name: 'Progresión' })
  await expect(progresion).toContainText('Am')
  await expect(progresion).toContainText('G')
  await expect(
    page.getByRole('list', { name: 'Diagramas de acordes' }).locator('svg'),
  ).toHaveCount(2)

  const guitarra = page.getByRole('group', { name: 'Guitarra' })
  await expect(
    guitarra.getByRole('button', { name: 'Clásica' }),
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('Arpegio', { exact: true })).toBeVisible()
  await guitarra.getByRole('button', { name: 'Eléctrica' }).click()
  await expect(page.getByText('Rasgueo', { exact: true })).toBeVisible()
  await guitarra.getByRole('button', { name: 'Clásica' }).click()
  await expect(page.getByText('Arpegio', { exact: true })).toBeVisible()
  await capturar(page, 'cancion-lista')
})

test('4. editar un acorde marca la sección como "Editado por vos"', async ({
  page,
}) => {
  await abrirCancion(page)
  await expect(page.getByText('Editado por vos')).toHaveCount(0)

  await page.getByRole('button', { name: 'Editar sección' }).click()
  await page.getByLabel('Acorde 1').fill('Em')
  await page.getByRole('button', { name: 'Guardar' }).click()

  await expect(page.getByText('Editado por vos')).toBeVisible()
  await expect(page.getByRole('list', { name: 'Progresión' })).toContainText(
    'Em',
  )

  await page.reload()
  await expect(page.getByText('Editado por vos')).toBeVisible()
  await capturar(page, 'cancion-editada')
})

test('5. "Practicar esta sección" crea un ejercicio y Terminé lo marca', async ({
  page,
}) => {
  await abrirCancion(page)
  await page.getByRole('button', { name: 'Practicar esta sección' }).click()
  await page.getByRole('button', { name: 'Crear ejercicio' }).click()
  await expect(
    page.getByRole('status').filter({ hasText: 'Listo' }),
  ).toBeVisible()

  const tarjeta = page.locator('.song-exercises .exercise-card')
  await expect(tarjeta).toHaveCount(1)
  await tarjeta.getByRole('button', { name: 'Terminé' }).click()
  await expect(tarjeta.getByText(/Tu mejor\s*\d+ bpm/)).toBeVisible()
  await capturar(page, 'cancion-ejercicio-terminado')
})

test('6. Progreso refleja el ejercicio de la canción', async ({ page }) => {
  await page.goto('/progreso')
  await expect(page.getByRole('heading', { name: 'Progreso' })).toBeVisible()
  const stat = (etiqueta: string) =>
    page.locator('.progress-stat').filter({ hasText: etiqueta })
  await expect(stat('Canciones en curso')).toContainText('1')
  await expect(stat('Racha actual')).toContainText(/[1-9]\d* día/)
  await expect(
    page
      .getByRole('img', { name: /^\d{2}\/\d{2}\/\d{4}: [1-9]\d* ejercicios?$/ })
      .first(),
  ).toBeVisible()
  await capturar(page, 'progreso-con-cancion')
})

test('7. la vista de canción no tiene scroll horizontal a 375 px', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await page.goto('/explorar')
  await expect(page.locator('.explore-song').first()).toBeVisible()
  const anchoExplorar = await page.evaluate(
    () => document.documentElement.scrollWidth,
  )
  expect(anchoExplorar, 'scrollWidth en /explorar').toBeLessThanOrEqual(375)

  await page.getByRole('link', { name: TITULO }).click()
  await expect(
    page.getByRole('list', { name: 'Diagramas de acordes' }),
  ).toBeVisible()
  await expect(page.locator('.song-exercises .exercise-card')).toHaveCount(1)
  const anchoCancion = await page.evaluate(
    () => document.documentElement.scrollWidth,
  )
  expect(anchoCancion, 'scrollWidth en la canción').toBeLessThanOrEqual(375)
  await capturar(page, 'cancion-375px')
})
