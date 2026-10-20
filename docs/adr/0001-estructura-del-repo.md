# 0001 — Estructura del repo

- Fecha: 2026-10-20
- Estado: aceptada
- Fase: 1

## Contexto

El proyecto tiene una API, una UI y contenido de currículo que se versionan juntos. Hace falta una estructura que separe dominio de infraestructura (la API no conoce yt-dlp, el pipeline no conoce FastAPI) y que sirva a la CI y a los agentes.

## Decisión

Monorepo con cuatro carpetas de primer nivel:

- `api/`: FastAPI, paquete `guitarra_api` con layout `src/` y subpaquetes `domain/`, `infra/` y `http/`.
- `ui/`: Vite + React + TypeScript, con vitest + Testing Library, eslint y prettier.
- `curriculum/`: contenido del currículo en JSON.
- `schemas/`: JSON Schema exportado desde los modelos.

La configuración de la API se lee por variables de entorno con `pydantic-settings` (`GUITAR_API_URL`, `GUITAR_API_TOKEN`, `DATABASE_URL`). La zona horaria no va por entorno: vive en la tabla `Settings`. La CI (GitHub Actions) corre dos jobs, `api` y `ui`, con los mismos comandos que en local.

## Alternativas consideradas

- Repos separados para API y UI: se descarta, es un proyecto personal de un solo usuario y los contratos cambian juntos.
- Layout plano sin `src/`: se descarta, el layout `src/` evita importar el paquete sin instalar y deja los tests honestos.

## Consecuencias

Un solo lugar para versionar contratos, esquemas y contenido. Hay que mantener dos toolchains (Python y Node) en la CI. Las carpetas `curriculum/` y `schemas/` se crean cuando haya contenido (tareas posteriores).
