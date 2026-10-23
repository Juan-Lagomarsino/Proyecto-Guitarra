# 0005 — Markdown en las lecciones con react-markdown

- Fecha: 2026-10-23
- Estado: aceptada
- Fase: 1

## Contexto

La teoría de cada lección (`content_md`) llega de la API como markdown y la UI tiene que mostrarla con formato (títulos, énfasis, listas). El contenido lo escribe Juan Pedro en el currículo, pero igual conviene que el render no pueda ejecutar HTML ni scripts. La UI debe seguir liviana y usar solo tokens CSS para el estilo.

## Decisión

Usar `react-markdown` para renderizar `content_md`, sin plugins de HTML crudo (`rehype-raw` no se instala). Por defecto la librería convierte el markdown en elementos de React y descarta el HTML embebido, así que no hay `dangerouslySetInnerHTML`. El estilo de los elementos se da por CSS con tokens en `StudyViews.css`.

## Alternativas consideradas

- `marked` o `markdown-it` + `dangerouslySetInnerHTML`: producen un string HTML que habría que sanear aparte (DOMPurify); más superficie de riesgo para un caso simple.
- `@mdx-js/react` / MDX: permite componentes dentro del texto, pero exige compilar y es mucho más pesado de lo que hace falta.
- Escribir las lecciones directamente en JSX: mezcla contenido con código y rompe el currículo como datos en la API.

## Consecuencias

- Se gana un render seguro por defecto y sin sanitizador propio.
- El HTML dentro del markdown no se muestra; si algún día hiciera falta (por ejemplo tablas, con `remark-gfm`), se agrega como plugin y se revisa en un ADR nuevo.
- Suma una dependencia con su árbol de remark/unified; hay que vigilar su tamaño en el bundle.
