# 0015 — Demucs: solo el modelo de 6 pistas

- Fecha: 2026-11-02
- Estado: aceptada
- Fase: 3

## Contexto

El plan pide separar con Demucs y deja la puerta abierta a usar también el modelo de 4 pistas. La Fase 3 necesita una sola cosa de la separación: la mezcla "sin guitarra" para tocar encima (ADR 0007 difirió Demucs hasta acá). Corre en el worker nativo, en CPU, y es el paso más pesado del sistema.

## Decisión

Se usa únicamente `htdemucs_6s` (drums, bass, other, vocals, guitar, piano). "Sin guitarra" = suma de las cinco pistas restantes con una ganancia global que deja el pico en -1 dBFS como máximo (no cambia el balance entre pistas). Es un desvío del plan, que también pedía el modelo de 4 pistas.

Por qué solo ese: es el único que aísla `guitar`; el de 4 pistas deja la guitarra dentro de `other`, así que no sirve para el objetivo. Tener los dos duplicaría el tiempo de CPU, los pesos a bajar y los archivos en caché, sin que ningún criterio de la fase use el de 4. Los pesos se bajan a `GUITAR_DEMUCS_MODEL_DIR` (default `GuitarApp\models\demucs`) con `scripts/install.ps1`; `demucs` va en el extra `separation` de `worker/pyproject.toml`, aparte de `analysis`, porque es pesado y opcional (sin él todo lo demás anda).

Costo estimado: en CPU de escritorio, de orden varios minutos por canción de 3-4 min (Demucs v4 en CPU suele andar cerca de 1x a 3x la duración del audio). **No se midió**: la nube de desarrollo no tiene acceso a Hugging Face, a dl.fbaipublicfiles.com ni al índice de PyTorch, así que la separación real se valida recién en la PC de Juan Pedro.

## Alternativas consideradas

- `htdemucs` de 4 pistas: no aísla la guitarra (queda en `other`).
- Los dos modelos (lo que decía el plan): el doble de CPU y espacio sin criterio que lo pida.
- Otros separadores (Spleeter, MDX): se descartan para no sumar otra dependencia cuando Demucs ya cubre el caso y es el del plan.
- Separar en GPU: el worker corre en CPU por decisión de entorno y la separación no es tiempo real.

## Consecuencias

- Calidad: la guitarra separada siempre deja algo de residuo en la mezcla; por eso la opción se marca "experimental" en la UI.
- Hay pistas en caché por canción (`stems/`, seis WAV float32); ocupan bastante disco y se pueden borrar sin romper nada (se vuelve a separar).
- Si luego se quisiera usar `guitar` o `piano` por separado (por ejemplo, para análisis), ya están en caché.
- Vigilar: tiempo real por canción en la PC, y la versión de `demucs` (PyPI publica 4.0.1; la API usada, `get_model` y `apply_model`, es la misma en 4.1).
