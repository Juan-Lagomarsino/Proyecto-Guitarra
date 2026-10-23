# 0010 — Paquete `core` compartido (teoría, acordes, instrumento)

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El diccionario de acordes y la adaptación al instrumento (capo, cejilla, power chords) los necesitan la API (diagramas y práctica) y el worker (acordes detectados que hay que mostrar con forma). El plan dejaba abierto si vivían en `api/.../domain/chord_shapes.py` o en un paquete compartido. El worker no debe importar la API (arrastraría FastAPI, SQLAlchemy y Postgres) y la API no debe importar el worker.

## Decisión

- Paquete `guitarra_core` en `core/`, Python puro y sin dependencias: `theory.py` (notas, acordes, transposición), `chord_shapes.py` (formas abiertas, con cejilla y power chords) e `instrument.py` (capo que minimiza cejillas, voicings para clásica y eléctrica).
- **No duplica el esquema de notación.** `ChordShape.to_notation()` devuelve `shape` y `barre` con la forma del modelo `Chord` de la API; la validación contra ese modelo vive en `api/tests/test_chord_shapes_notation.py`. Así el validador sigue en un solo lugar.
- Instalación: la imagen de la API instala `core` antes que la API (`api/Dockerfile`); `scripts/install.ps1` lo instala editable en el venv del worker; en CI hay un job `core` y los jobs `api` y `worker` lo instalan con `pip install -e ../core`.
- Ni la API ni el worker lo declaran como dependencia en su `pyproject.toml` por ahora (no hay índice de paquetes): se instala por ruta, siempre primero.

## Alternativas consideradas

- Dentro de `api/domain`: obliga al worker a depender de la API o a duplicar el código.
- Duplicar en `worker/`: dos diccionarios que divergen.
- Declarar `guitarra-core @ file:../core` en los pyproject: las rutas relativas fallan en el build de Docker y complican `pip install -e`.
