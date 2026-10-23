# 0006 — Herramientas de análisis de canciones

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El worker tiene que sacar tempo y compases, acordes, tonalidad y estructura de una canción, en Windows 11 + Python 3.12 + CPU, sin compilar nada raro. Se midieron los candidatos con las 5 canciones del repertorio (audio de YouTube bajado a la caché local, WAV 48 kHz). Scripts y resultados crudos: `spikes/analisis/` (ver su README para reproducir). Referencias: BPM de songbpm.com y acordes de Cifra Club (fixtures en `worker/tests/fixtures/cifraclub/`).

Limitaciones de la medición, para no sobreinterpretarla:

- Cifra Club no trae tiempos y escribe cada sección una sola vez. La coincidencia de acordes se mide por sección: se normaliza cada acorde a (raíz, mayor/menor), se reduce la sección a su ciclo mínimo y se busca el mejor tramo de la progresión detectada (distancia de edición). "Coincide" = puntaje >= 0.75; "exacta" = 1.0. Control negativo: la misma métrica con los 11 desplazamientos de tonalidad equivocados da 0-2 % de exactas, o sea que la métrica no regala aciertos.
- No hay compases ni secciones con tiempos de referencia: para compases se usa un proxy (qué parte de los cambios de acorde de BTC cae en los downbeats declarados) y para estructura solo proxies (acuerdo entre variantes y con los cambios de BTC).
- `cerca-del-fuego` no tiene referencia de Cifra Club (ver Consecuencias): solo cuenta para BPM y tiempos. `no-voy-en-tren` tiene la cifra como una lista plana de 12 acordes sin repeticiones, incomparable por sección (todas las herramientas puntúan bajo).

## Mediciones

### Tempo (BPM contra referencia; tiempo de proceso sin cargar el modelo)

| Canción | Ref | beat_this | librosa |
| --- | --- | --- | --- |
| Flaca | 109 | 111.1 (+1.9 %) · 7.9 s | 107.7 (-1.2 %) · 3.3 s |
| De música ligera | 124 | 125.0 (+0.8 %) · 5.0 s | 123.0 (-0.8 %) · 0.5 s |
| Boys Don't Cry | 169 | 166.7 (-1.4 %) · 3.8 s | **83.4 (-50.7 %, mitad)** · 0.4 s |
| Cerca del fuego | 115 | 115.4 (+0.3 %) · 3.2 s | 117.5 (+2.1 %) · 0.4 s |
| No voy en tren | 124 | 125.0 (+0.8 %) · 4.4 s | 123.0 (-0.8 %) · 0.4 s |

### Compases (proxy: fracción de cambios de acorde sobre los downbeats declarados)

| Canción | beat_this | librosa |
| --- | --- | --- |
| Flaca | 0.88 | 0.89 |
| De música ligera | 0.50 | 0.48 |
| Boys Don't Cry | 1.00 | 0.33 |
| Cerca del fuego | 0.29 | 0.47 |
| No voy en tren | 0.80 | 0.72 |

Los dos dan 4 beats por compás en las cinco. Donde el proxy es bajo en ambos (ligera, cerca) también lo es la "mejor fase" posible: los acordes no cambian al compás, no es necesariamente un error de downbeat. El proxy no distingue.

### Acordes (por sección contra Cifra Club: % coincide / % exacta / puntaje medio · tiempo por canción)

| Canción (secciones) | BTC voca | BTC majmin | Chordino | Plantillas (chroma + Viterbi) |
| --- | --- | --- | --- | --- |
| Flaca (5) | 100 / 100 / 1.00 · 2.6 s | 100 / 100 / 1.00 · 2.2 s | 100 / 100 / 1.00 · 5.4 s | 100 / 100 / 1.00 · 21.1 s |
| De música ligera (10) | 100 / 100 / 1.00 · 1.3 s | 100 / 100 / 1.00 · 1.2 s | 100 / 100 / 1.00 · 4.3 s | 100 / 10 / 0.78 · 7.8 s |
| Boys Don't Cry (12) | 100 / 100 / 1.00 · 1.0 s | 100 / 100 / 1.00 · 1.1 s | 100 / 42 / 0.91 · 3.5 s | 100 / 42 / 0.91 · 6.2 s |
| No voy en tren (1, plana) | 0 / 0 / 0.64 · 1.1 s | 0 / 0 / 0.64 · 1.1 s | 0 / 0 / 0.55 · 3.9 s | 0 / 0 / 0.46 · 8.3 s |
| Cerca del fuego (sin ref) | 0.9 s | 0.9 s | 3.2 s | 8.4 s |

El desplazamiento libre óptimo fue 0 en todas, o sea que las fixtures (capo 0) coinciden con el audio sin transponer.

Instalación: BTC = clonar `jayg996/BTC-ISMIR19` (MIT, trae los pesos, 34 MB) con dos arreglos de compatibilidad (`yaml.safe_load` y el alias `np.float`); corre en CPU con torch. Chordino = el paquete `vamp` de pip no tiene rueda para Windows y exige compilar; se usó el DLL de `nnls-chroma` extraído del instalador del Vamp Plugin Pack más Sonic Annotator (ejecutable suelto), sin instalar nada en el sistema.

### Tonalidad (Krumhansl-Schmuckler; "relativa" = mayor/menor relativo)

| Canción | Ref | KS sobre chroma | KS sobre acordes de BTC | KS sobre plantillas |
| --- | --- | --- | --- | --- |
| Flaca | G | G (exacta) | G (exacta) | G (exacta) |
| De música ligera | Bm | D (relativa) | D (relativa) | D (relativa) |
| Boys Don't Cry | A | A (exacta) | A (exacta) | A (exacta) |
| No voy en tren | A | A (exacta) | A (exacta) | A (exacta) |
| Cerca del fuego | sin ref | C | Am | Am |

Tiempo: 0.7-3 s por canción (chroma); la variante sobre los acordes de BTC sale gratis del paso de acordes.

### Estructura (autosimilitud con librosa sobre la grilla de beats de beat_this; 1-30 s por canción)

| Canción | Secciones (novedad / aglomerativo) | Cifra Club | Acuerdo entre variantes | Acuerdo de la novedad con cambios de BTC |
| --- | --- | --- | --- | --- |
| Flaca | 7 / 15 | 5 | 0.20 | 0.18 |
| De música ligera | 11 / 12 | 10 | 0.48 | 0.00 |
| Boys Don't Cry | 12 / 13 | 12 | 0.61 | 0.15 |
| Cerca del fuego | 2 / 7 | — | 0.00 | 0.00 |
| No voy en tren | 10 / 10 | 1 (plana) | 0.78 | 0.33 |

El conteo de la novedad se acerca a Cifra Club en ligera y Boys, pero en el resto las variantes casi no coinciden entre sí: la estructura automática es poco confiable.

## Decisión

| Paso | Elección | Números clave |
| --- | --- | --- |
| Tempo y compases | **beat_this** (beats y downbeats) | BPM dentro de +-2 % de la referencia en 5/5; librosa falla Boys Don't Cry (mitad de tempo, -51 %) y su proxy de compases cae a 0.33. 3-8 s por canción en CPU. |
| Acordes | **BTC, vocabulario `voca`**, sobre la mezcla | 100 % coincide y 100 % exacta en las 3 canciones comparables por sección; 1-2.6 s por canción, el más rápido. `voca` da calidades (7, sus, etc.) que `majmin` no, al mismo costo. |
| Tonalidad | **Krumhansl-Schmuckler sobre el histograma de acordes de BTC** | Exacta en 3/4, relativa (D por Bm) en 1/4; sin costo extra. Se reporta con confianza baja porque confunde relativas. |
| Estructura | **Autosimilitud (librosa, variante novedad) sobre la grilla de beats**, con nombres y orden de secciones de Cifra Club cuando exista (F2-T10) | Proxies flojos: la detección sola no alcanza; Cifra Club aporta nombres y repeticiones, la detección aporta los tiempos. Sin Cifra Club, secciones sin nombre y confianza baja. |

Todo instala con pip (más el clon de BTC) y corre en Windows 11 + Python 3.12 + CPU, sin compilar.

## Alternativas consideradas

- **madmom** (beats/downbeats): descartado. No hay rueda para Python 3.12 en Windows (`pip download` falla) y exigiría compilar Cython; además está sin mantenimiento.
- **librosa `beat_track`** (tempo): descartado como principal. Rápido (0.4 s) pero divide el tempo (Boys Don't Cry a 83 BPM) y los downbeats son una suposición de fase. Posible respaldo barato.
- **Chordino** (nnls-chroma): descartado. Misma coincidencia que BTC (100 %) pero exacta 42 % en Boys Don't Cry contra 100 %, 2-4 veces más lento (3-5 s), y exige sacar DLL de un instalador de GUI y usar Sonic Annotator porque `vamp` de pip no instala en Windows sin compilar. Plan B si BTC deja de servir.
- **BTC `majmin`**: descartado. Resultados idénticos a `voca` en lo medido, pero solo mayor/menor.
- **Plantillas de tríadas sobre chroma CQT + Viterbi** (línea base propia): descartado. Exacta 10 % en ligera y 42 % en Boys; 6-21 s por canción.
- **MSAF** (estructura): descartado. Instala (0.1.80) pero falla al importar con scipy actual (`from scipy import inf`); proyecto sin mantenimiento.
- **Segmentación aglomerativa de librosa**: probada junto a la novedad. Sobresegmenta (15 secciones en Flaca) y no mejora el acuerdo; queda como variante ajustable en T09.
- **basic-pitch** (transcripción): no se midió; el plan lo ubica en la Fase 5 (riffs).

## Consecuencias

- Los pasos F2-T07, T08 y T09 usan estas herramientas. BTC se instala desde su repo fijando un commit (MIT) y aplicando los dos parches, desde el `install.ps1` del worker; hay que fijar el commit.
- Desvío de implementación (F2-T08): los dos parches de BTC (`yaml.safe_load` y el alias `np.float`) no los aplica `install.ps1` sobre el clon; los aplica `adapters/btc.py` en tiempo de ejecución al cargar el modelo. `install.ps1` solo clona BTC en el commit fijo `2682317`, y el clon queda limpio.
- **beat_this: el host oficial de los pesos (`cloud.cp.jku.at`) devolvió 503** durante el spike. Se usó un espejo safetensors y `beat_this_checkpoint.py` completó los buffers `rotary_embed.freqs`. `install.ps1` tiene que bajar el checkpoint con reintentos y caer al espejo; vigilar.
- Cifra Club es la referencia para nombres de secciones y acordes y pesa más que cualquier modelo de audio. Sin cifra, esperar tonalidad y acordes razonables y estructura pobre, y mostrar la confianza.
- **Sin referencia de Cifra Club para `cerca-del-fuego`**: la página no existe en el archivo web (Wayback no tiene la URL), el sitio devuelve 403 a pedidos automáticos y el archivo de 2015 de la página del artista lista 0 cifras. La fixture queda marcada `disponible: false`. F2-T19 tiene que cargar la progresión a mano o validar esa canción solo por oído.
- `no-voy-en-tren`: la cifra es plana; el comparador por sección no aplica. Revisión manual en T19.
- La métrica por sección es una aproximación (sin tiempos). Si T19 muestra errores de tiempo, anotar a mano una canción con tiempos.
- Tiempos: la tanda completa (beat_this + BTC + tonalidad + estructura) ronda 10-40 s por canción en CPU, sin contar la descarga.
