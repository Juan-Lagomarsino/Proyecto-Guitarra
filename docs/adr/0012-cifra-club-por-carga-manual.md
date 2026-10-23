# 0012 — Cifra Club por carga manual

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 2

## Contexto

El plan (§ Pipeline, paso 8) pide buscar la canción en Cifra Club por título y artista y cruzar sus acordes con los detectados. En F2-T10 se comprobó que Cifra Club responde 403 (Akamai, "Access Denied") a todo pedido automático, aun con User-Agent de navegador. Esquivar esa protección no corresponde. El parser y la alineación ya están hechos y probados con HTML grabado.

## Decisión

Juan Pedro carga la cifra a mano. En la vista de canción pega el texto de la cifra, copiado de la página de Cifra Club, y opcionalmente el link como referencia. La API lo guarda en la canción (`songs.cifra_text`, `songs.cifra_url`) y encola un reanálisis. El trabajo reclamado lleva `cifra_text`. El paso de Cifra Club del worker parsea ese texto, sin hacer ningún pedido HTTP, y lo alinea con lo detectado. Sin texto, el paso devuelve "sin datos" y el pipeline sigue.

El criterio 3 de la fase queda así: "Cruce con Cifra Club cuando el usuario cargó la cifra; sin cifra, o si no se puede parsear, el pipeline termina igual."

## Alternativas consideradas

- Scraping directo: bloqueado por el sitio; evadir la protección no es aceptable.
- Internet Archive: la cobertura es incierta y las copias pueden estar viejas; agrega otra dependencia de red para un resultado no garantizado.
- Las dos (Archive con carga manual de respaldo): más código para poco beneficio en una app de un solo usuario.

## Consecuencias

- El cruce deja de ser automático: una canción nueva se analiza sin Cifra Club hasta que Juan Pedro pegue la cifra.
- Se elimina el cliente HTTP de Cifra Club (y su configuración de URL e intervalo entre pedidos). El parser pasa a aceptar texto plano (secciones `[Intro]`, líneas de acordes, `Tom:` y capo); si se pega HTML, se usa el parser de HTML existente.
- La caché del paso tiene que invalidarse cuando cambia el texto (por ejemplo, con el hash del texto en la clave).
- Implementación (F2-T13): el parser de texto es `parse_cifraclub_text` (HTML si trae `<pre`, si no texto plano: una línea es de acordes si todos sus tokens son acordes o marcas como `(2x)`, `|`, `N.C.`; las secciones `[Tab ...]` se ignoran). La clave de caché usa un `cache_token(job)` opcional del paso (hash del texto): al cambiar la cifra se rehacen `cifraclub` y todos los pasos siguientes (`strum`, `assemble`), no los anteriores.
- Implementación (F2-T13): el armado usa los nombres de la cifra solo si la similitud global de la alineación es >= 0.6; en ese caso también pisa los nombres de sección con los de la cifra y, en clásica, usa el capo de la cifra (sin cifra buena, el que sugiere `guitarra_core`). La sección queda con `chord_source: "cifraclub"` si más de la mitad de sus acordes se emparejaron.
- El criterio 4 (coincidencia con Cifra Club en la mayoría de las secciones) no cambia: se mide contra las fixtures de T01.
- Validación (F2-T19, `docs/fases/fase-2/validacion.md`): el umbral 0.6 se mantuvo. Las cifras que alinean dan similitud 0.74 a 0.91 y la lista plana de "No voy en tren" da 0.09, así que hay margen a los dos lados. Limitación conocida: la alineación es global (la cifra entera contra todo lo detectado), por eso solo sirve si la cifra escribe la canción completa, con las repeticiones (así son las 4 páginas de las fixtures). Una cifra que escribe cada sección una sola vez (como el texto corto `text/flaca.txt`, similitud 0.13) cae en "solo detectado". Mejora posible: alinear el ciclo de cada sección contra la sección detectada.
- Ajuste (F2-T21): si la alineación global no alcanza (< 0.6), el armado alinea el ciclo de cada sección de la cifra contra cada sección detectada (`domain/section_alignment.py`, `GOOD_SECTION_MATCH = 0.6`, mínimo 3 acordes detectados por sección). Una sola transposición para toda la canción (se prueba 0, la del capo de la cifra y las demás); con empate entre secciones de la cifra con la misma progresión, los nombres se reparten en orden. Las secciones que coinciden toman nombre y acordes de la cifra (`chord_source: "cifraclub"`); el resto queda detectado. Si ninguna coincide, la cifra no se usa y la UI avisa ("La cifra cargada no coincidió con lo que se escucha; se usaron los acordes detectados."). `text/flaca.txt` pasa de 0 a 5 de 6 secciones con la cifra. El parser toma `A/` como `A`.
