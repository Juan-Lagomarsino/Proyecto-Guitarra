# Currículum

Cada archivo `curriculum/*.json` define **un nivel** con sus lecciones y ejercicios. El cargador (`python -m guitarra_api.infra.curriculum_loader`) los lee todos, valida cada `notation` con el modelo `Notation` (ADR 0003) y hace upsert en la base al arrancar la API. Nunca borra nada, así que las completions se conservan.

Carpeta configurable con `GUITAR_CURRICULUM_DIR` (en Docker: `/app/curriculum`).

## Formato

```json
{
  "level": {
    "slug": "nivel-02-pentatonica",
    "position": 2,
    "name": "Pentatónica menor",
    "description": "Texto corto del nivel.",
    "instrument": "electric"
  },
  "lessons": [
    {
      "slug": "caja-1",
      "position": 1,
      "title": "La caja 1",
      "content_md": "Teoría corta en **markdown**, atada a lo que se toca.",
      "exercises": [
        {
          "slug": "pentatonica-la-caja-1-subiendo",
          "title": "Caja 1 de La, subiendo y bajando",
          "type": "scale",
          "category": "technique",
          "bpm_start": 60,
          "bpm_target": 100,
          "duration_min": 4,
          "description": "Subí y bajá por la caja 1 con púa alternada. Cuidá que cada nota suene pareja.",
          "notation": { "bpm": 60, "tonic": "A", "events": [] }
        }
      ]
    }
  ]
}
```

| Campo | Regla |
| --- | --- |
| `level.slug` | Minúsculas, números y guiones; único entre todos los archivos. Es la clave de upsert del nivel. |
| `level.position` | Entero único entre todos los archivos. Solo ordena. |
| `level.instrument` | `classical` o `electric`; los ejercicios heredan el del nivel. |
| `lessons[].slug` | Único dentro del nivel. Clave de upsert de la lección (junto con el nivel). |
| `lessons[].position` | Entero único dentro del nivel. Solo ordena; se puede insertar una lección en el medio renumerando. |
| `exercises[].slug` | Minúsculas, números y guiones; **único y estable** en todo el currículum. Es la clave de upsert: si lo cambiás, se crea un ejercicio nuevo y el viejo queda con sus completions. |
| `exercises[].type` | `scale`, `riff`, `chords`, `strumming`, `arpeggio`, `technique` o `improvisation`. |
| `exercises[].category` | `warmup`, `technique`, `riff` o `improvisation` (lo usa la sesión del día). |
| `bpm_start`, `bpm_target`, `duration_min` | Enteros positivos, con `bpm_target >= bpm_start`. |
| `exercises[].description` | **Obligatorio.** Texto de 1 a 3 frases (máx. 500 caracteres, sin espacios sobrantes): qué se toca, en qué fijarse y un consejo práctico. La UI lo muestra en la tarjeta del ejercicio. |
| `notation` | Formato de notación del plan (`schemas/notation.schema.json`). `notation.bpm` debe ser igual a `bpm_start`. |

El cargador valida esas reglas antes de escribir en la base y, si algo falla, informa archivo y slug.

**Lo que sale del JSON no se borra de la base:** si quitás un nivel, lección o ejercicio del archivo, sigue en la base (y en la app). Es deuda conocida.

## Convenciones de contenido

- Español rioplatense, teoría corta y atada a lo que se toca.
- Riffs originales "al estilo de"; nunca transcripciones de canciones con copyright.
- Power chords: `shape` va de la 6ta a la 1ra cuerda; el nombre es `<tónica>5` y `tonic` debe estar entre las tónicas de los acordes (lo verifica `api/tests/test_curriculum_content.py`).
- Técnicas de dos notas (`h`, `p`, `/`, `\`) en la nota de destino.

## Agregar un nivel

1. Crear `curriculum/nivel-NN-<tema>.json` con el formato de arriba.
2. Correr `pytest api/tests/test_curriculum_content.py`: valida esquema, slugs, rangos de tempo y música.
3. Al reiniciar la API, el cargador lo incorpora.
