# CLAUDE.md — App de Práctica de Guitarra

App personal para practicar guitarra (Estudio, Explorar, Rig, Progreso). El plan completo, con arquitectura, contratos y criterios de aceptación, está en `docs/PLAN.md`. **Leelo antes de cualquier tarea.** Si algo de este archivo choca con el plan, gana el plan y se avisa.

## Entorno

- PC de escritorio con **Windows 11** (definitivo). Shell: PowerShell. Rutas con `pathlib`, nunca separadores fijos.
- API + Postgres + UI en **Docker Desktop** (WSL2). Worker y Rig en **Python 3.12 nativo** con venv: nunca en Docker (no ven ASIO ni la GPU).
- Naxxon (Ubuntu Server) todavía no está operativo. No se despliega nada ahí hasta la Fase 7.
- Usuario único: Juan Pedro. Habla español rioplatense; la UI, los commits y los ADR van en español.

## Metodología: orquestador + devs + revisor

La sesión principal (**Opus**) es el **orquestador**. No escribe código de producción salvo arreglos de integración de pocas líneas. Su trabajo es planificar, delegar, integrar y cuidar el plan.

### Roles

| Rol | Modelo | Qué hace | Definición |
| --- | --- | --- | --- |
| Orquestador | Opus (sesión principal) | Parte la fase en tareas, delega, integra, commitea, habla con Juan Pedro | este archivo |
| `dev` | Sonnet | Implementa UNA tarea con sus tests | `.claude/agents/dev.md` |
| `revisor` | Sonnet | Revisa el diff de una tarea contra su criterio y el plan; no edita | `.claude/agents/revisor.md` |
| `runner` | Haiku | Tareas mecánicas: correr tests y lint, formatear, redactar ADR a partir de notas, actualizar docs | `.claude/agents/runner.md` |

### Ciclo de una fase

1. **Planificar.** El orquestador lee la fase en `docs/PLAN.md` y escribe `docs/fases/fase-N.md` con la lista de tareas. Cada tarea tiene: id (`F1-T03`), objetivo en una línea, archivos o módulos que toca, criterio de aceptación verificable, dependencias.
   - Tareas chicas: que un `dev` las termine en una sola corrida (idealmente < 400 líneas de diff).
   - Marcar cuáles son independientes (pueden ir en paralelo) y cuáles dependen de otras.
2. **⏸ Aprobación de Juan Pedro.** Mostrar el plan de tareas y esperar el OK antes de delegar. Es una de las dos paradas obligatorias.
3. **Delegar.** Por cada tarea, lanzar un `dev` con un prompt autocontenido (ver plantilla abajo). Las tareas independientes van en paralelo, cada una en su propio worktree (`isolation: "worktree"`) para que no se pisen.
4. **Revisar.** Cuando un `dev` termina, lanzar un `revisor` sobre ese diff. Si el revisor marca problemas bloqueantes, el mismo `dev` (vía SendMessage) los corrige; máximo 2 vueltas, después decide el orquestador.
5. **Integrar.** El orquestador mergea, corre la suite completa (o se la pide a un `runner`), y hace **commit + push** de la tarea. Marca la tarea como hecha en `docs/fases/fase-N.md`.
6. **Cerrar la fase.** Verificar uno por uno los criterios de aceptación de la fase en el plan, con evidencia (test que pasa, comando y salida, captura). Escribir el resumen en `docs/fases/fase-N.md`.
7. **⏸ Demo a Juan Pedro.** Segunda parada obligatoria: mostrar qué quedó, cómo probarlo y qué criterios se cumplen. No arrancar la fase siguiente sin su OK.

Fuera de esas dos paradas, el orquestador trabaja solo. Solo frena antes si: una decisión del plan resulta inviable, hay que gastar plata, o algo no se puede deshacer.

### Plantilla de prompt para un `dev`

```
Tarea F<N>-T<NN>: <objetivo en una línea>
Contexto: <qué parte del plan aplica, con la sección de docs/PLAN.md>
Archivos/módulos: <dónde trabajar; qué no tocar>
Criterio de aceptación: <verificable>
Dependencias ya hechas: <tareas previas y qué dejaron>
Al terminar: tests pasando, sin commitear, y reportá qué cambiaste, cómo lo probaste y qué quedó dudoso.
```

### Ahorro de consumo

- El orquestador no lee archivos grandes que puede resumir un subagente; pide conclusiones, no volcados.
- Lo mecánico (correr tests, lint, formatear, mover docs) va al `runner` en Haiku.
- Nada de lanzar agentes para preguntas que se responden leyendo un archivo.
- Un `dev` por tarea, no uno por archivo.

## Reglas de código

- **Clean Code y SOLID.** Funciones chicas, nombres claros, sin lógica duplicada. Dominio separado de infraestructura (la API no conoce yt-dlp; el pipeline no conoce FastAPI).
- **Tests en todo módulo.** Backend: `pytest`. Frontend: `vitest` + Testing Library. Lógica de dominio (racha, sesión del día, notación, digitación) con casos de borde.
- **Formato y lint:** Python con `ruff` (lint + format); TypeScript con `eslint` + `prettier`. La CI corre lo mismo que se corre local.
- **Formato de notación único** (ver plan): todo lo que se toca se guarda en ese JSON. Si hace falta un campo nuevo, se cambia el esquema y su validador en un solo lugar.
- **Configuración por variables de entorno** (`GUITAR_API_URL`, token, rutas de audio). Nada de rutas ni secretos fijos en el código. `.env.example` siempre al día; `.env` nunca se commitea.
- **En vivo no corre IA ni análisis.** El camino del Rig es guitarra → ASIO → cadena VST3 con preset cargado → auriculares. Ollama y el worker nunca participan del audio en tiempo real.
- Colores de la UI solo por tokens CSS. Ningún color fijo en componentes.

## Git

- Repo privado en GitHub. **Commit + push al cerrar cada tarea**; nunca dejar trabajo sin pushear al final de una sesión.
- Commits en español, formato Conventional Commits: `feat(estudio): cálculo de racha con días excluidos`.
- Rama `main` siempre verde. Trabajo en paralelo en worktrees y ramas `f<N>-t<NN>-<slug>`.
- `.gitattributes`: `* text=auto eol=lf`, `*.ps1 eol=crlf`.

## Decisiones (ADR)

Cada decisión técnica va en `docs/adr/NNNN-titulo.md` con la plantilla de `docs/adr/0000-plantilla.md`. Obligatorio cuando: se elige una librería entre varias, se desvía del plan, o se descarta algo. Si una decisión del plan resulta inviable, ADR primero y avisar; no improvisar en silencio.

## Skills

Usar estas skills cuando apliquen (instalación en el README):

- **superpowers** (obra/superpowers):
  - `subagent-driven-development` — guía el ciclo dev + revisión de dos etapas; seguirla al delegar tareas.
  - `dispatching-parallel-agents` y `using-git-worktrees` — para tareas independientes en paralelo.
  - `test-driven-development` — los `dev` escriben primero el test que falla, después el código.
  - `systematic-debugging` — ante cualquier bug o test rojo, antes de proponer arreglos.
  - `verification-before-completion` — nada se marca como hecho sin evidencia.
  - No usar `brainstorming` ni `writing-plans` de superpowers: el plan ya existe y el ciclo de fases de este archivo los reemplaza.
- **anthropics/skills**:
  - `frontend-design` — para el mástil, la tablatura, las tarjetas y el tema; respetar el estilo del artefacto de referencia.
  - `webapp-testing` — para verificar la UI con Playwright al cerrar cada fase.

## Comandos útiles

Se completan a medida que existan:

```powershell
docker compose up -d          # API + Postgres + UI
.\scripts\install.ps1         # worker y Rig (idempotente)
pytest                        # tests backend
npm test --prefix ui          # tests frontend
```
