# 0007 — Demucs pasa a la Fase 3

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El plan (§ Pipeline de análisis) pone la separación de pistas con Demucs como paso 3, antes de tempo y acordes. Ningún criterio de aceptación de la Fase 2 usa pistas separadas, y Demucs en CPU es el paso más lento y pesado del pipeline. La Fase 3 sí lo necesita para la mezcla "sin guitarra". La decisión de partida de `docs/fases/fase-2.md` dice: si el spike muestra que los acordes mejoran mucho con pistas armónicas, se vuelve a traer.

## Decisión

Demucs se difiere a la Fase 3. En la Fase 2 el análisis (tempo, acordes, tonalidad, estructura) corre sobre la mezcla original. El spike (ADR 0006) no justifica traerlo de vuelta: BTC sobre la mezcla completa coincide al 100 % por sección con Cifra Club en las 3 canciones comparables (Flaca, De música ligera, Boys Don't Cry). Lo único flojo es `no-voy-en-tren`, y es un problema de la referencia (una cifra plana de 12 acordes, no comparable por sección), no del audio. No se midió el efecto de pistas armónicas: no había nada que mejorar en lo medido, así que Demucs no se instaló en el spike.

## Alternativas consideradas

- Mantener Demucs en la Fase 2 como dice el plan original: suma minutos de CPU por canción y modelos grandes sin que ningún criterio lo pida.
- Usar pistas armónicas solo para acordes: sin evidencia de ganancia en las canciones medidas; se reevalúa en la Fase 3 con Demucs ya instalado, sobre todo si F2-T19 detecta errores de acordes en canciones densas.

## Consecuencias

- El pipeline de la Fase 2 queda más corto: decenas de segundos por canción en CPU en vez de minutos.
- La separación entra en la Fase 3 como un paso más del pipeline con caché (la interfaz de pasos ya lo permite); de ahí salen los `AudioAsset` `sin_guitarra` y `stems`.
- Cuando entre, conviene repetir la evaluación de acordes con la mezcla sin voz como segunda medición; los scripts de `spikes/analisis/` sirven para eso.
