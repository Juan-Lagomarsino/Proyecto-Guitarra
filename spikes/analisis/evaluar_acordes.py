"""Métrica de acordes contra Cifra Club (definición en docs/adr/0006).

Cifra Club no trae tiempos y escribe cada sección una sola vez (aunque se repita en la
canción), así que no se alinea por tiempo. Para cada sección de la referencia:

1. Se normaliza cada acorde a (raíz en semitonos, mayor/menor): enarmónicos iguales,
   `Am7`, `A/E`, `Asus4` -> A menor/mayor; las extensiones se ignoran.
2. Se colapsan repeticiones consecutivas y se reduce la sección a su ciclo mínimo
   (Bm G D A Bm G D A ... -> Bm G D A).
3. Se busca el mejor tramo de la progresión detectada (alineación semiglobal por
   distancia de edición). Puntaje = 1 - distancia / largo del ciclo.
4. La sección "coincide" si el puntaje es >= 0.75 (a lo sumo un acorde de cuatro distinto)
   y "exacta" si es 1.0.

La progresión detectada se limpia antes: sin N/X, sin tramos de menos de 0,4 s, sin repeticiones.
Transposición: `capo` suma los semitonos del capo a la referencia (todas las fixtures tienen capo 0);
`libre` prueba los 12 desplazamientos y elige uno por canción (el que más puntaje total da).
"""

import json
import re
import sys
from pathlib import Path

from acordes_comun import SALIDA, leer_linea
from songs import SONGS

FIXTURES = (
    Path(__file__).resolve().parents[2] / "worker" / "tests" / "fixtures" / "cifraclub"
)
ACCIDENTE = {"": 0, "#": 1, "♯": 1, "b": -1, "♭": -1}
PITCH = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MIN_SEG = 0.4
UMBRAL = 0.75


def normalizar(etiqueta: str) -> tuple[int, bool] | None:
    """'F#m7/C#' o 'F#:min' -> (6, True) = F# menor. None para N/X/ilegibles."""
    base = etiqueta.split("/")[0].strip()
    m = re.match(r"^([A-G])([#b♯♭]?)(.*)$", base)
    if not m:
        return None
    raiz = PITCH[m.group(1)] + ACCIDENTE[m.group(2)]
    resto = m.group(3).lstrip(":")
    es_menor = bool(re.match(r"^(m(?!aj)|min|dim|hdim)", resto))
    return raiz % 12, es_menor


def sin_repetidos(secuencia: list) -> list:
    return [x for i, x in enumerate(secuencia) if i == 0 or x != secuencia[i - 1]]


def ciclo_minimo(secuencia: list) -> list:
    n = len(secuencia)
    for p in range(1, n + 1):
        if all(secuencia[i] == secuencia[i % p] for i in range(n)):
            return secuencia[:p]
    return secuencia


def limpiar_detectado(tramos: list) -> list[tuple[int, bool]]:
    acordes = []
    for ini, fin, etiqueta in tramos:
        if fin - ini < MIN_SEG:
            continue
        a = normalizar(etiqueta)
        if a is not None:
            acordes.append(a)
    return sin_repetidos(acordes)


def distancia_semiglobal(patron: list, texto: list) -> int:
    """Distancia de edición mínima entre `patron` y cualquier tramo de `texto`."""
    prev = [0] * (len(texto) + 1)
    for i, p in enumerate(patron, 1):
        actual = [i]
        for j, t in enumerate(texto, 1):
            costo = 0 if p == t else 1
            actual.append(min(prev[j - 1] + costo, prev[j] + 1, actual[j - 1] + 1))
        prev = actual
    return min(prev)


def puntaje_seccion(acordes_ref: list, detectado: list, desplazamiento: int) -> float:
    ciclo = ciclo_minimo(sin_repetidos(acordes_ref))
    ciclo = [((r + desplazamiento) % 12, m) for r, m in ciclo]
    return 1 - distancia_semiglobal(ciclo, detectado) / len(ciclo)


def cargar_referencia(slug: str) -> dict | None:
    ruta = FIXTURES / f"{slug}.json"
    if not ruta.exists():
        return None
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    secciones = []
    for s in datos["sections"]:
        acordes = [a for a in (normalizar(c) for c in s["chords"]) if a is not None]
        if acordes:
            secciones.append((s["name"], acordes))
    return {"capo": datos["capo"], "secciones": secciones}


def evaluar(herramienta: str, slug: str) -> dict | None:
    ref = cargar_referencia(slug)
    if ref is None:
        return None
    detectado = limpiar_detectado(leer_linea(herramienta, slug)["tramos"])

    def total(desp: int) -> float:
        return sum(puntaje_seccion(a, detectado, desp) for _, a in ref["secciones"])

    mejor = max(range(12), key=total)
    resultado = {"n_secciones": len(ref["secciones"]), "desplazamiento_libre": mejor}
    for nombre, desp in (("capo", ref["capo"]), ("libre", mejor)):
        puntajes = [puntaje_seccion(a, detectado, desp) for _, a in ref["secciones"]]
        resultado[nombre] = {
            "coincide": round(sum(p >= UMBRAL for p in puntajes) / len(puntajes), 3),
            "exacta": round(sum(p >= 1.0 for p in puntajes) / len(puntajes), 3),
            "puntaje_medio": round(sum(puntajes) / len(puntajes), 3),
        }
    # Control negativo: la misma métrica con los 11 desplazamientos equivocados.
    erroneos = [d for d in range(12) if d != mejor]
    falsos = [
        sum(puntaje_seccion(a, detectado, d) >= 1.0 for _, a in ref["secciones"])
        / len(ref["secciones"])
        for d in erroneos
    ]
    resultado["control_exacta"] = round(sum(falsos) / len(falsos), 3)
    return resultado


if __name__ == "__main__":
    herramientas = sys.argv[1:] or sorted(p.name for p in SALIDA.iterdir())
    salida = {}
    for h in herramientas:
        salida[h] = {}
        for slug in SONGS:
            r = evaluar(h, slug)
            if r:
                salida[h][slug] = r
                print(h, slug, r)
    (Path(__file__).parent / "resultados" / "acordes_metricas.json").write_text(
        json.dumps(salida, indent=2), encoding="utf-8"
    )
