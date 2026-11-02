import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:18000'
// Opcional: un Chromium ya instalado (Linux sin `playwright install`). En Windows no se define.
const executablePath = process.env.E2E_CHROMIUM_PATH || undefined

// Los tests son un recorrido ordenado sobre una base vacía: un solo worker, en serie.
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          executablePath,
          // La reproducción nace de un clic, pero así no depende del gesto en el navegador de CI.
          args: ['--autoplay-policy=no-user-gesture-required'],
        },
      },
    },
  ],
})
