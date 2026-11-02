# 0016 — Síntesis del backing con Web Audio

- Fecha: 2026-11-02
- Estado: aceptada
- Fase: 3

## Contexto

La Fase 3 necesita metrónomo y un backing generado (batería, bajo y acordes) que suene en el navegador. El ADR 0004 eligió Web Audio pelado para el metrónomo y dejó Tone.js para reevaluar en esta fase. Se quiere que el reloj del backing sea el mismo que el de la práctica (ADR 0004) y que no haya que descargar nada para empezar a tocar.

## Decisión

Usar Web Audio API pelada, sin Tone.js ni samples. Tres piezas en `ui/src/backing/` y `ui/src/audio/`:

- `arrangement.ts`: función pura que convierte el chart en eventos ubicados en beats. No sabe nada de audio.
- `synth.ts`: `WebAudioVoiceSink`, que dibuja cada voz con nodos nativos. Bombo con seno y caída de pitch; redoblante con ruido pasabanda más un tono; hi-hat con ruido pasa-altos; bajo con sierra y pasa-bajos; acordes con pad triangular. El clic es compartido con el metrónomo en `ui/src/audio/clickTone.ts`. Al cancelar se hace un fade-out de unos 25 ms para no cortar en seco.
- `generatedSource.ts`: implementa `BackingSource` (ADR 0014) con el reloj del ADR 0004, un lookahead de 100 ms y un tick de 25 ms. Soporta velocidad y loop A-B a través de la misma interfaz.

## Alternativas consideradas

- Tone.js: unos 100 kB, trae sintetizadores y transporte propio. Habría que adaptar el reloj del ADR 0004 a su transporte, y el beneficio no compensa el peso para timbres tan simples.
- Samples de batería: hay que versionar archivos o bajarlos en runtime, y sumar licencias para revisar. Más complejo que sintetizar cuatro voces.
- Render en el worker como WAV: los cambios de tempo no quedan exactos, aumenta la cantidad de archivos y el backing depende del worker. Se mantiene como posible camino para el Rig en la Fase 4b.

## Consecuencias

Cero dependencias nuevas. Los timbres van a sonar simples, "de juguete", y hay que escucharlos en la PC antes de darlos por buenos. La lógica de tiempo (arrangement, scheduler con lookahead, loop A-B) es testeable con un reloj falso. El sintetizador real no tiene tests significativos en jsdom: solo se prueba contra un `AudioContext` falso mínimo, así que la validación del sonido es manual. En la Fase 4b, cuando el backing salga por el Rig, hay que decidir si el Rig sintetiza con la misma lógica o si el backing se renderiza a archivo.
