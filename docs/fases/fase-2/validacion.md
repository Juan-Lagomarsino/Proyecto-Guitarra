# Fase 2: validación con las 5 canciones (F2-T19, parte A)

Fecha: 2026-10-23. Máquina de Juan Pedro (Windows 11, CPU, Python 3.12, torch 2.14.1 CPU). Modelos reales:
beat_this (tempo y compases), librosa (estructura), BTC `voca` (acordes), Krumhansl-Schmuckler (tonalidad).
El audio sale de la caché del spike T01 (`GuitarApp/cache/spike/*.wav`, WAV 48 kHz estéreo).

Reproducir:

```powershell
cd worker
.\.venv\Scripts\python tests\validacion\validar_canciones.py --json salida.json
```

El script (`worker/tests/validacion/validar_canciones.py`; la métrica está en `metrica.py` y sus tests en
`tests/test_validacion_metrica.py`) reemplaza los pasos `source` y `download` por el audio ya bajado y corre
los demás pasos reales del registro (`default_steps`, sin Ollama para que sea determinista: rasgueo por
reglas). No es parte de la suite de CI.

## Definición de "la sección coincide"

Se mide sobre el chart eléctrico que arma el worker. Los nombres del chart son los de altura real, así que la
transposición del capo ya está resuelta de ese lado; el capo de la cifra se le suma a la referencia.

1. Cada acorde se normaliza a (raíz en semitonos, mayor/menor): enarmónicos iguales; extensiones, bajos y
   sus se ignoran. Se sacan los ilegibles (N.C.) y las repeticiones seguidas.
2. Cada sección de la referencia (fixture de Cifra Club) se reduce a su ciclo mínimo (Bm G D A Bm G D A pasa a Bm G D A).
3. Una sección del chart coincide con una de la referencia si (a) puntaje: el más corto de los dos (ciclo o
   sección) se encuentra dentro del más largo (el ciclo se repite) con distancia de edición, y
   `1 - distancia / largo del patrón >= 0.75` (a lo sumo un acorde de cuatro distinto); (b) pureza: al menos
   75 % de los acordes de la sección pertenecen al conjunto del ciclo; (c) el patrón tiene al menos
   min(largo del ciclo, 3) acordes.
4. Se toma la mejor sección de la referencia. En el modo b, si la sección del chart se llama como una
   de la referencia (los nombres vienen de la cifra), se compara solo con las de ese nombre.
5. Segunda cifra, "% ref": porcentaje de secciones de la referencia cuyo ciclo aparece en el flujo de
   acordes de toda la canción detectada (puntaje >= 0.75). Es la métrica del spike T01.

Dos modos: **a** sin cifra (solo detección; las secciones salen como "Parte A, B, ...") y **b** con la
cifra cargada como texto (flujo del ADR 0012). La cifra del modo b se arma desde la fixture JSON como texto
plano estilo Cifra Club (`[Sección]` y una línea de acordes); es la página completa, con repeticiones.

Casos especiales:

- **Cerca del fuego**: `disponible: false`, sin referencia. Solo cuentan BPM, tiempo y que el pipeline termine;
  no hay % de secciones ni modo b (no hay cifra que cargar).
- **No voy en tren**: la cifra es una lista plana de 12 acordes en una sola sección sin repeticiones (A, D, F,
  G, A, D, A, F, G, A, E7), así que no hay ciclo que buscar. Se la trata como el vocabulario de la canción: una
  sección coincide si al menos 75 % de sus acordes (con raíz y calidad) están en esa lista y usa 2 o más
  acordes distintos. "% ref" pasa a ser qué parte de los acordes de la lista aparece en lo detectado.

## Resultados

| Canción | BPM ref | BPM | error | tonalidad | a: % secciones | a: % ref | b: % secciones | b: % ref | t a (s) | t b (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Flaca | 109 | 109.4 | +0.4 % | G | 100 % (6/6) | 100 % (5/5) | 100 % (6/6) | 100 % (5/5) | 12.3 | 0.1 |
| De música ligera | 124 | 124.0 | 0.0 % | D | 90 % (9/10) | 100 % (10/10) | 90 % (9/10) | 100 % (10/10) | 8.1 | 0.2 |
| Boys Don't Cry | 169 | 166.6 | -1.4 % | A | 100 % (11/11) | 100 % (12/12) | 100 % (11/11) | 100 % (12/12) | 6.2 | 0.1 |
| Cerca del fuego | 115 | 115.1 | +0.1 % | Am | n/a | n/a | n/a | n/a | 5.3 | n/a |
| No voy en tren | 124 | 123.6 | -0.3 % | A | 60 % (6/10) | 100 % (vocab.) | 60 % (6/10) | 100 % (vocab.) | 6.9 | 0.0 |

- BPM de referencia: songbpm.com (los de T01, `spikes/analisis/songs.py`). Las 5 quedan dentro de +-2 %.
- Tiempos: pipeline completo sin descarga (tempo, estructura, acordes, tonalidad, rasgueo y armado) con la caché de
  pasos vacía y el modelo ya cargado. El primer arranque de todos (importar torch, leer pesos, caché de disco fría)
  tardó 28.9 s en Flaca. Desglose de Flaca: tempo 7.8 s, estructura 2.8 s, acordes 1.6 s, el resto menos de 0.1 s.
  "t b" es lo que cuesta reanalizar con la cifra: solo se rehacen `cifraclub`, `strum` y `assemble`.
- Similitud de la alineación con la cifra (modo b): Flaca 0.741, De música ligera 0.905, Boys Don't Cry 0.795,
  No voy en tren 0.091 (la cifra no se usa, queda `detected`). En las tres primeras todas las secciones, salvo la
  última de De música ligera, quedan con `chord_source: cifraclub`, y el capo clásico pasa a ser el de la cifra (0).
- Sin cifra, el capo clásico lo propone `guitarra_core` (`best_capo`): 7 en Flaca, De música ligera y Boys Don't Cry; 5 en las otras dos (primera pasada; corregido en F2-T21, ver más abajo).

### Qué falla y por qué

- **De música ligera, 9/10**: la última sección (7 acordes detectados, pureza 0.43) es el final desvanecido. La
  referencia "Final" tiene 2 acordes y BTC mete acordes de paso que no están en la cifra. En el modo b esa sección queda
  `detected` porque la mayoría de sus acordes no se emparejó. Es el comportamiento esperado.
- **No voy en tren, 6/10 (60 %)**: la cifra es una lista de 12 acordes y la canción real es casi toda A-D alternados.
  Las 4 secciones que fallan tienen Am, Am7, D7 o Dm (calidad menor donde la cifra dice mayor: puede ser una confusión
  de BTC entre A y Am o pasos modales de la canción; no se puede decidir sin un chart manual). Cumple "la mayoría" (más
  de 50 %) pero con poco margen y con una referencia pobre. En el modo b la cifra no se usa (similitud 0.09), así que a y b
  son iguales. No se bajó el umbral de la métrica para que dé más: sería ajustar la vara a la respuesta.

### Salvedades de la métrica

- En canciones de progresión repetitiva (Flaca, De música ligera) todas las secciones del chart comparten la
  progresión de la referencia, así que "coincide" es fácil. Por eso se reporta también la pureza y el modo b compara por
  nombre de sección. Aun así, el nombre de sección sale de alinear acordes y dos secciones con la misma progresión se
  pueden confundir (Flaca: la 2.ª sección sale "Intro" en vez de "Refrão", con acordes idénticos). El acierto del nombre no
  se mide porque la referencia no tiene tiempos.
- En el modo b una parte de la coincidencia es por construcción (los nombres vienen de la cifra); el modo a es el que
  mide la detección sola.
- Cerca del fuego: la estructura devolvió solo 2 secciones (107 acordes en total, confianza baja). Sin referencia no hay
  forma de saber si es razonable; hay que mirarla de oído.

## Ajustes

Primera pasada (F2-T19): ninguno. `GOOD_ALIGNMENT = 0.6` se mantiene: las cifras buenas dan 0.74 a 0.91 y la lista plana 0.09.

Segunda pasada (F2-T21), a partir de lo que mostró la primera:

1. **Cifra por sección.** La alineación global descartaba, sin avisar, una cifra que escribe cada sección una sola vez
   (`text/flaca.txt`, similitud 0.13). Ahora, si la global no alcanza, `domain/section_alignment.py` compara el ciclo mínimo
   de cada sección de la cifra (repetido, con la mejor rotación) contra los acordes de cada sección detectada, con una sola
   transposición para toda la canción (0, la del capo, las demás). Se toman los nombres solo en las secciones con similitud
   >= `GOOD_SECTION_MATCH` (0.6); el resto queda detectado. Lo global no cambia: las cifras completas dan los mismos resultados.
2. **Aviso en la UI.** Con cifra cargada, análisis listo y ninguna sección `cifraclub`, la vista de canción muestra que la
   cifra no coincidió y se usaron los acordes detectados.
3. **Capo sugerido.** Causa (por qué salía 7): el costo se sumaba por acorde detectado y el castigo por traste era fijo (0.25),
   así que en una canción entera (100 a 200 acordes) el castigo no pesaba nada y cualquier ruido (un `B` mayor suelto en
   Flaca, que pide cejilla) inclinaba la balanza. Capo 7 ganaba por 11 puntos de 309 (3.7 %). Ahora se compara el costo medio por
   acorde con 0.1 por traste, el máximo por defecto baja de 7 a 5, con empate gana 0 y si las formas más fáciles de la progresión
   no llevan cejilla no se propone capo.
4. **Parser.** `A/` (barra sin bajo) se toma como `A`, en texto y en HTML. Se corrigió la fixture de No voy en tren.

## Re-validación (F2-T21)

Mismo audio y mismos modelos que arriba. Las columnas de coincidencia no cambiaron (los acordes detectados son los mismos):

| Canción | a: % secciones | a: % ref | b: % secciones | b: % ref | capo clásica a (antes) | capo clásica b | b: secciones con cifra |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Flaca | 100 % (6/6) | 100 % (5/5) | 100 % (6/6) | 100 % (5/5) | 0 (7) | 0 | 6/6 |
| De música ligera | 90 % (9/10) | 100 % (10/10) | 90 % (9/10) | 100 % (10/10) | 0 (7) | 0 | 9/10 |
| Boys Don't Cry | 100 % (11/11) | 100 % (12/12) | 100 % (11/11) | 100 % (12/12) | 2 (7) | 0 | 11/11 |
| Cerca del fuego | n/a | n/a | n/a | n/a | 5 (5) | n/a | n/a |
| No voy en tren | 60 % (6/10) | 100 % (vocab.) | 60 % (6/10) | 100 % (vocab.) | 0 (5) | 0 | 1/10 (antes 0/10) |

- **Cifra corta de Flaca** (`text/flaca.txt`, 19 acordes, cada sección una vez): antes 0 secciones con cifra (similitud global 0.135);
  ahora **5 de 6** secciones con `chord_source: "cifraclub"` y los nombres de la cifra. La sexta (detectada como otra cosa) queda
  detectada. Coincidencia contra la referencia: 100 % (6/6) en el chart y 100 % de la referencia. Capo clásica 2: el del texto
  de esa cifra (el fixture dice "2ª casa"; es un texto armado a mano, no la página real).
- Boys Don't Cry sin cifra sigue pidiendo capo 2 (Am Bm G C en vez de Bm C#m A D: baja de dos cejillas a una); ya no el 7.
  La cifra real dice capo 0, y con ella se usa 0.
- No voy en tren (modo b): la lista plana de 12 acordes ahora toma una sección por el camino por sección. No cambia el
  porcentaje. La sección de la cifra sin encabezado tiene nombre vacío (antes "(sin título)") y el armado usa el nombre
  detectado ("Parte B", etc.).
- Los tiempos de la tabla anterior no se re-midieron (se reusó la caché de pasos de audio; las columnas de arriba son del
  pipeline completo en la primera pasada). Pasos nuevos (`cifraclub`, `strum`, `assemble`): menos de 1 s por canción.

Reproducir la cifra corta: `validar_canciones.py --only flaca --cifra-file tests/fixtures/cifraclub/text/flaca.txt`.

## Limitación que quedó resuelta: cifras que escriben cada sección una sola vez

(Texto original, antes de T21.) La alineación de `domain/alignment.py` era global. El texto corto `flaca.txt` daba similitud 0.13 y
terminaba con `chord_source: detected` sin avisar. Ahora se alinea por sección y la UI avisa si nada coincide. El caso de
la corrida por la API (más abajo) es el de antes del ajuste.

## Corrida de punta a punta por la API

Se reconstruyó la imagen (`docker compose up -d --build`; la que corría era anterior a T20 y no tenía `/cifra`). La base
estaba vacía. El worker usa `GUITAR_WORKER_TOKEN` del `.env`.

```powershell
curl.exe -X POST localhost:8000/api/v1/songs -H "Authorization: Bearer $env:GUITAR_API_TOKEN" `
  -H "Content-Type: application/json" -d '{"url":"https://www.youtube.com/watch?v=UCF9oHXhDMU"}'
# 201 {"id":1,"source":"youtube","analysis_status":"queued",...}
.\worker\.venv\Scripts\python -m guitarra_worker --once      # descarga real con yt-dlp, 37 s en total
```

- `GET /songs/1`: `analysis_status: ready`, bpm 109.44, key G, duración 272.091 s.
- `GET /songs/1/chart?instrument=classical`: versión 1, origen `auto`, confianza 0.90, 6 secciones "Parte A..F"
  (`detected`), capo 7, rasgueo `rasgueo-4-balada` y arpegio `arpegio-4-pima` en cada sección, `sources` con yt-dlp,
  beat_this, librosa, btc-voca, krumhansl-schmuckler y ollama (acá sí corrió el chooser de Ollama, qwen2.5:3b).
- `GET ...instrument=electric`: versión 1, confianza 0.92, capo 0, 6 secciones, rasgueo sin arpegio (el arpegio es solo clásica).
- `PUT /songs/1/cifra` con `worker/tests/fixtures/cifraclub/text/flaca.txt` (el texto corto): `reanalysis_queued: true`; el
  worker reanalizó (pasos de audio desde la caché; `cifraclub`, `strum` y `assemble` en 6 s) y quedó la versión 2, pero con
  `chord_source: detected` (similitud 0.13, ver la limitación). `has_cifra: true`.
- `PUT /songs/1/cifra` con el texto completo de Flaca (render de la fixture JSON, 529 caracteres): versión 3,
  **`chord_source: "cifraclub"` en las 6 secciones**, nombres de sección de la cifra (Intro, Intro, Primeira Parte,
  Refrão, Solo Final, Solo Final), capo clásico 0 y `cifraclub-texto` en `sources`.

Limpieza: no hay `DELETE /songs/{id}`, así que la canción de prueba se borró con SQL en la base de Docker
(`DELETE FROM songs WHERE id = 1`; en cascada se fueron trabajos, charts y secciones; las tablas quedaron en 0 filas,
como estaban). Quedan en disco, fuera del repo, el audio y la caché de pasos en `GuitarApp/cache/UCF9oHXhDMU` y
`GuitarApp/cache/validacion`.

## Suite del worker

`pytest`: 323 pasaron, 0 omitidos (con torch instalado corren también el test de beat_this con clicks y el de BTC real).
`ruff check .` y `ruff format --check .`: sin errores.

## Conclusiones

- BPM: 5/5 dentro de +-2 % de la referencia.
- Acordes por sección: 90 a 100 % en Flaca, De música ligera y Boys Don't Cry, en los dos modos. No voy en tren llega
  a 60 % (mayoría, pero contra una referencia plana). Cerca del fuego no tiene referencia.
- Criterio "la mayoría de las secciones coincide en las 5 canciones": se cumple en las 4 con referencia; la quinta
  (Cerca del fuego) se valida solo por BPM, tiempo y de oído.
- Velocidad: 5 a 12 s por canción de 3 a 5 minutos.
- A mejorar: calidad mayor/menor en No voy en tren. (La alineación para cifras de secciones únicas se resolvió en F2-T21.)
