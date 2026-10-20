# App de Práctica de Guitarra

Plan: `docs/PLAN.md` · Reglas para agentes: `CLAUDE.md`.

## Preparar el entorno (escritorio Windows)

1. Instalar Git, Python 3.12, Node LTS y Docker Desktop (backend WSL2).
2. Clonar este repo y abrir Claude Code en la carpeta.
3. Instalar las skills que usa el proyecto (en Claude Code):

   ```
   /plugin install superpowers@claude-plugins-official
   /plugin marketplace add anthropics/skills
   /plugin install example-skills@anthropic-agent-skills
   ```

   La primera trae `subagent-driven-development`, `test-driven-development`, `systematic-debugging`, `verification-before-completion` y las de paralelismo; la segunda trae `frontend-design` y `webapp-testing`.
4. Elegir el modelo del orquestador: `/model opus`.

## Arrancar una fase

> Leé `docs/PLAN.md` y `CLAUDE.md`. Arrancá la Fase 1 siguiendo la metodología de `CLAUDE.md`: armá el plan de tareas y mostrámelo antes de delegar.
