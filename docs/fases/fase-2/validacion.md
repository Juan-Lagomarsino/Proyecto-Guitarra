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
- Sin cifra, el capo clásico lo propone `guitarra_core` (`best_capo`): 7 en Flaca, De música ligera y Boys Don't Cry; 5 en las otras dos.

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

Ninguno. `GOOD_ALIGNMENT = 0.6` se mantiene: las cifras buenas dan 0.74 a 0.91 y la lista plana 0.09, hay margen
a los dos lados. No hizo falta tocar el snap a beats ni los umbrales de confianza. La limitación de la alineación
global quedó anotada en el ADR 0012.

## Limitación encontrada: cifras que escriben cada sección una sola vez

La alineación de `domain/alignment.py` es global: la secuencia entera de la cifra contra toda la detectada. Las 4 cifras
de las fixtures JSON son la canción completa con repeticiones, y alinean. Pero el texto corto
`fixtures/cifraclub/text/flaca.txt` (19 acordes, cada sección una vez) da similitud 0.13 contra los 141 acordes
detectados: el análisis termina bien pero con `chord_source: detected`, sin avisar al usuario que la cifra no se usó
(probado en la corrida por la API, abajo). Pendiente de decidir: alinear el ciclo de cada sección de la cifra contra las
secciones detectadas, o avisar en la UI.

Detalle menor: el parser deja fuera `A/` (barra sin bajo) de la lista de No voy en tren.

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
- A mejorar: alineación para cifras de secciones únicas; calidad mayor/menor en No voy en tren.
