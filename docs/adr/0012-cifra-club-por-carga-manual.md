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
- El criterio 4 (coincidencia con Cifra Club en la mayoría de las secciones) no cambia: se mide contra las fixtures de T01.
