/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // GUITAR_API_URL se lee del .env de la raíz del repo o del entorno.
  const env = loadEnv(mode, '..', 'GUITAR_')
  const apiUrl = env.GUITAR_API_URL || 'http://localhost:8000'

  return {
    // Las VITE_* del cliente también salen del .env de la raíz.
    envDir: '..',
    plugins: [react()],
    server: {
      proxy: { '/api': apiUrl },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      // Los tests leen los .css como texto (tokens, colores literales).
      css: { include: /.+/ },
      setupFiles: ['./src/setupTests.ts'],
    },
  }
})
