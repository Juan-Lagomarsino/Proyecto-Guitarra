# 0002 — UI servida por la API

- Fecha: 2026-10-20
- Estado: aceptada
- Fase: 1

## Contexto

La app es de un solo usuario y corre en localhost. Hace falta que `docker compose up` deje todo andando sin un servidor web aparte para la UI, y que en desarrollo se pueda iterar rápido sobre la UI.

## Decisión

Un solo contenedor `api` con build multi-etapa: una etapa de Node construye `ui/dist` y la imagen final de Python lo copia. FastAPI sirve `index.html` en `/`, los archivos de `/assets` y, para cualquier otra ruta que no sea `/api`, vuelve a `index.html` (rutas de la SPA). La carpeta de la UI compilada se configura con `GUITAR_UI_DIST`; si no existe, la API arranca igual sin servir la UI.

En desarrollo, Vite corre aparte con proxy de `/api` hacia la API.

El `entrypoint.sh` corre `alembic upgrade head` y después uvicorn, así las migraciones son automáticas al levantar. Los puertos se publican solo en `127.0.0.1` y Postgres usa un volumen nombrado.

## Alternativas consideradas

- Contenedor nginx aparte para la UI: se descarta, agrega un servicio y CORS/proxy sin beneficio para un usuario único.
- Servir la UI solo con Vite: se descarta, no es un despliegue (ni sirve para Naxxon más adelante).

## Consecuencias

Un solo origen (sin CORS) y un solo servicio para desplegar. El build de la imagen tarda más porque compila la UI. Un cambio de UI requiere reconstruir la imagen (en desarrollo se usa Vite).
