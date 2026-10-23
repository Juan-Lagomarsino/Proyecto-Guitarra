# 0011 — Modelo local (Ollama) para elegir el rasgueo

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El chart de cada canción lleva un rasgueo (y, en clásica, un arpegio p-i-m-a). El plan pide usar un LLM local solo para elecciones acotadas, con esquema JSON y validación, y que el pipeline no dependa de él. Juan Pedro eligió un modelo chico (~2 GB, tipo `qwen2.5:3b`).

## Decisión

- **Catálogo** en `worker/src/guitarra_worker/strum/catalog.json`: patrones con id, nombre, tipo (`strum` o `arpeggio`), compás (`beats_per_bar`), estilo y complejidad 1 a 4. Los `pattern` y `accent` tienen el formato del esquema de notación (ADR 0003 y 0008); `api/tests/test_strum_catalog_notation.py` los valida contra los modelos de la API, sin duplicar el validador. El arpegio p-i-m-a de clásica son entradas propias del mismo catálogo.
- **Reglas puras** (`strum/rules.py`): filtran por compás exacto (3/4 no recibe patrones de 4/4; compases sin patrones dan "sin datos") y topan la complejidad por tempo (hasta 90 bpm: 4; hasta 120: 3; hasta 150: 2; más: 1). La densidad de ataques por beat es una entrada opcional; T12 no la mide del audio. Sin densidad se apunta a complejidad 3.
- **Ollama** (`strum/ollama_chooser.py`) elige solo entre los candidatos que dejaron las reglas, vía `/api/chat` con `format` = JSON Schema con `enum` de ids, `temperature` 0 y timeout. La respuesta se vuelve a validar: id fuera de la lista, JSON roto, HTTP de error, timeout o conexión rechazada son `ChooserError` y se cae a las reglas (`strum/selection.py`). El paso `strum` nunca falla por el LLM.
- Un patrón por canción (una llamada al LLM por tipo), que T13 aplica a todas las secciones. Confianza propuesta: reglas 0.4, Ollama 0.6.
- Config: `GUITAR_OLLAMA_URL` (vacío = solo reglas), `GUITAR_OLLAMA_MODEL`, `GUITAR_OLLAMA_TIMEOUT_S`.

## Alternativas consideradas

- Solo reglas: no aprovecha el estilo de la canción (título y artista).
- Que el LLM genere el patrón libremente: viola "nada de generar con el LLM"; el catálogo garantiza que todo valida.
- Elegir por sección: multiplica las llamadas y el modelo chico no tiene más información por sección.

## Consecuencias

- Con Ollama apagado el resultado es determinista y el pipeline sigue.
- Un modelo de 3B sabe poco de cada canción: la elección es una preferencia de estilo, no una verdad; la corrección manual (T17) manda.
- Hay que vigilar el tiempo de la primera llamada (carga del modelo): el timeout por defecto es 30 s.
