import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

// Acompañamiento de la canción que deja z-canciones (orden alfabético: "zz" va después, misma base).
// Audio sintético (tono + clics, 20 s) subido como si fuera el worker.
test.describe.configure({ mode: 'serial' })

const CAPTURAS = path.resolve(
  import.meta.dirname,
  '../../docs/fases/fase-3/capturas',
)
const AUDIO = fs.readFileSync(
  path.resolve(import.meta.dirname, '../fixtures/audio-sintetico.m4a'),
)
const TOKEN_WORKER =
  process.env.E2E_WORKER_TOKEN ?? 'e2e-worker-token-de-prueba'
const TITULO = 'Canción de prueba'

const capturar = (page: Page, nombre: string) =>
  page.screenshot({ path: path.join(CAPTURAS, `${nombre}.png`) })

declare global {
  interface Window {
    __audios: HTMLAudioElement[]
  }
}

test.beforeAll(() => {
  fs.mkdirSync(CAPTURAS, { recursive: true })
})

// La fuente crea un `new Audio()` suelto (no está en el DOM): se lo captura al construirse.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.__audios = []
    const Original = window.Audio
    window.Audio = function (src?: string) {
      const audio = new Original(src)
      window.__audios.push(audio)
      return audio
    } as unknown as typeof Audio
  })
})

const campoDelAudio = (page: Page, campo: 'currentTime' | 'playbackRate') =>
  page.evaluate((c) => window.__audios.at(-1)?.[c] ?? -1, campo)

async function abrirCancion(page: Page) {
  await page.goto('/explorar')
  await page.getByRole('link', { name: TITULO }).click()
  await expect(
    page.getByRole('heading', { name: TITULO, exact: true }),
  ).toBeVisible()
}

const panel = (page: Page) =>
  page.getByRole('region', { name: 'Acompañamiento' })

const opcion = (page: Page, nombre: string) =>
  panel(page).getByRole('radio', { name: new RegExp(nombre) })

const reproducir = async (page: Page) => {
  await panel(page).getByRole('button', { name: 'Reproducir' }).click()
  await expect(
    panel(page).getByRole('button', { name: 'Pausar' }),
  ).toBeVisible()
}

// No hay listado de trabajos: se prueba con ids correlativos hasta dar con uno existente. El
// router acepta cualquier trabajo de la canción, aunque ya esté cerrado.
async function subirOriginal(request: APIRequestContext): Promise<void> {
  for (let jobId = 1; jobId <= 20; jobId++) {
    const respuesta = await request.post(
      `/api/v1/jobs/${jobId}/assets/original`,
      {
        data: AUDIO,
        headers: {
          Authorization: `Bearer ${TOKEN_WORKER}`,
          'Content-Type': 'audio/mp4',
        },
      },
    )
    if (respuesta.status() === 404) continue
    expect(respuesta.status(), await respuesta.text()).toBeLessThan(300)
    return
  }
  throw new Error('No se encontró ningún trabajo existente para subir el audio')
}

test('1. el worker (simulado) sube el audio original sintético', async ({
  request,
}) => {
  await subirOriginal(request)
})

test('2. el panel muestra las 4 opciones y "sin guitarra" deshabilitado con su motivo', async ({
  page,
}) => {
  await abrirCancion(page)
  await expect(panel(page).getByRole('radio')).toHaveCount(4)
  for (const nombre of [
    'Metrónomo',
    'Original',
    'Sin guitarra',
    'Backing generado',
  ]) {
    await expect(opcion(page, nombre)).toBeVisible()
  }
  await expect(opcion(page, 'Original')).toBeEnabled()
  await expect(opcion(page, 'Sin guitarra')).toBeDisabled()
  // Al cerrar el análisis la API encola la separación: el motivo es que sigue en curso.
  await expect(panel(page)).toContainText('separando…')
  await capturar(page, 'panel-acompanamiento')
})

test('3. Original: avanza la posición, 50 % conserva el tono y el loop vuelve al inicio', async ({
  page,
}) => {
  await abrirCancion(page)
  await opcion(page, 'Original').check()
  await reproducir(page)
  await expect
    .poll(() => campoDelAudio(page, 'currentTime'), { timeout: 10_000 })
    .toBeGreaterThan(0.5)

  await panel(page).getByLabel('Velocidad').fill('50')
  await expect(panel(page)).toContainText('50 %')
  await expect.poll(() => campoDelAudio(page, 'playbackRate')).toBe(0.5)
  const conserva = await page.evaluate(
    () => window.__audios.at(-1)?.preservesPitch,
  )
  expect(conserva, 'preservesPitch').toBe(true)
  await capturar(page, 'original-50')

  // Loop de la sección elegida (Intro, 0–12 s): al pasar el fin, la posición vuelve al inicio.
  await panel(page)
    .getByRole('button', { name: /Repetir sección/ })
    .click()
  await page.evaluate(() => {
    window.__audios.at(-1)!.currentTime = 11.5
  })
  await expect
    .poll(() => campoDelAudio(page, 'currentTime'), { timeout: 10_000 })
    .toBeLessThan(5)
  await expect(
    page.locator('.song-timeline__button[data-looping="true"]'),
  ).toContainText('Intro')
})

test('4. Backing generado y Metrónomo: el resaltado de sección y acorde se mueve', async ({
  page,
}) => {
  await abrirCancion(page)
  const acordeAhora = page.locator('.song-progression__chord[data-now="true"]')

  await opcion(page, 'Backing generado').check()
  await reproducir(page)
  await expect(
    page.locator('.song-timeline__button[data-now="true"]'),
  ).toContainText('Intro')
  // Intro: primer acorde a 1 s (z-canciones lo editó a Em), segundo a 7 s (G).
  await expect(acordeAhora).toHaveText('Em', { timeout: 10_000 })
  await capturar(page, 'backing-generado')
  await expect(acordeAhora).toHaveText('G', { timeout: 15_000 })

  await opcion(page, 'Metrónomo').check()
  await expect(
    panel(page).getByRole('button', { name: 'Pausar' }),
  ).toBeVisible()
  await expect(page.locator('[data-now="true"]').first()).toBeVisible()
  await capturar(page, 'metronomo')
})

test('5. la vista de canción con el panel no tiene scroll horizontal a 375 px', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await abrirCancion(page)
  await expect(panel(page)).toBeVisible()
  const ancho = await page.evaluate(() => document.documentElement.scrollWidth)
  expect(ancho, 'scrollWidth en la canción con panel').toBeLessThanOrEqual(375)
  await capturar(page, 'acompanamiento-375px')
})
