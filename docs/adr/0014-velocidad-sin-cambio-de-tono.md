# 0014 — Velocidad sin cambio de tono con lo nativo del navegador

- Fecha: 2026-11-02
- Estado: aceptada
- Fase: 3

## Contexto

Para practicar hay que bajar la velocidad del acompañamiento (50 % a 100 %) sin que cambie el tono. El acompañamiento se reproduce con un `<audio>`. Se prefiere no sumar dependencias.

## Decisión

Usar `playbackRate` con `preservesPitch = true` (y `mozPreservesPitch` / `webkitPreservesPitch` si existen), acotado a [0,5; 1,0]. El loop A-B se vigila en cada cuadro con `Clock.onFrame` (no con `timeupdate`, que es lento) y la posición se lee siempre de `currentTime`. Todo vive detrás de la interfaz `BackingSource` (`ui/src/backing/`).

## Alternativas consideradas

- SoundTouchJS: procesa en JS/AudioWorklet; suma dependencia y latencia, y no hace falta si lo nativo alcanza.
- Rubber Band WASM: mejor calidad a velocidades bajas, pero pesa más y complica la integración y el empaquetado.

## Consecuencias

Cero dependencias y poco código. La calidad depende del navegador: se reevalúa (SoundTouchJS o Rubber Band WASM) si a 50 % no convence al escucharlo. Al estar detrás de `BackingSource`, el cambio no toca la vista.
