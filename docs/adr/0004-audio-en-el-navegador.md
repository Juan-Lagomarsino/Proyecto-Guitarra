# 0004 — Audio en el navegador: Web Audio pelado para el metrónomo

- Fecha: 2026-10-20
- Estado: aceptada
- Fase: 1

## Contexto

La Fase 1 necesita reproducción del ejercicio (modo automático y nota por nota) y un metrónomo con acento en el 1, sincronizados con el transporte. El plan menciona Tone.js para el backing de la Fase 3. En la Fase 1 el único sonido es un clic; las notas se resaltan en la tablatura y el mástil, no se sintetizan.

## Decisión

Web Audio pelado, sin dependencias nuevas. El tiempo sale de `AudioContext.currentTime` a través de una interfaz `Clock` inyectable (`now()` y `every()`); los clics se programan con anticipación (lookahead de 100 ms, despertar cada 25 ms) con osciladores. `setInterval` solo despierta al planificador; nunca es la fuente de verdad del tiempo. En tests se inyecta un `FakeClock`.

La interfaz `Clock` y `ClickSink` aísla el motor del navegador: si en la Fase 3 se adopta Tone.js, alcanza con una implementación nueva de `Clock` (sobre `Tone.getContext()`/`Transport`) sin tocar el motor ni el hook.

## Alternativas consideradas

- Tone.js ya: suma ~100 kB y un transporte propio para generar un clic; el motor ya tiene su transporte (ancla en beats, cambio de BPM en vivo) y es testeable con reloj falso. Se reevalúa en la Fase 3, cuando haya backing, loops y sincronización con audio.
- `setInterval`/`setTimeout` como reloj: se desvía y se atrasa con la pestaña en segundo plano; descartado como fuente de tiempo.

## Consecuencias

Sin dependencia nueva y lógica de tiempo pura y testeable. Cuesta mantener un planificador propio (chico, ~40 líneas). `currentTime` no compensa `outputLatency`: el resaltado de la UI puede adelantarse unos ms al sonido. La UI se actualiza con `requestAnimationFrame` (intervalo de 25 ms como fallback); el planificador del audio es independiente y sigue con su lookahead. El AudioContext se cierra al desmontar y se crea en el primer `play`; pausa, parada y cambio de BPM cancelan los clics ya agendados (política de autoplay: el contexto nace en un gesto del usuario). En segundo plano los navegadores aceleran los timers, pero los clics ya agendados siguen sonando a tiempo.
