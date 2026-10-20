# Contexto de build: la raíz del repo (ver docker-compose.yml).

# Etapa 1: compila la UI.
FROM node:22-slim AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Etapa 2: API + UI compilada.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    GUITAR_UI_DIST=/app/ui-dist
COPY api/pyproject.toml ./
COPY api/src ./src
RUN pip install --no-cache-dir .
COPY api/alembic.ini ./
COPY api/alembic ./alembic
COPY api/entrypoint.sh ./
COPY --from=ui /ui/dist ./ui-dist
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
