"""Métrica de "la sección coincide con Cifra Club" (lógica pura; definición en validacion.md).

Cada acorde se normaliza a (raíz en semitonos, menor sí/no): enarmónicos iguales y extensiones
(7, sus, bajos) ignoradas. Una sección de la referencia se reduce a su ciclo mínimo. Una sección del
chart coincide con una de la referencia si:

- puntaje: el más corto de los dos (ciclo o sección) se encuentra dentro del más largo (el ciclo se
  repite) con distancia de edición, y 1 - distancia / largo del patrón >= UMBRAL;
- pureza: al menos UMBRAL de los acordes de la sección pertenecen al conjunto de la referencia;
- y el patrón tiene al menos min(largo del ciclo, MIN_PATRON) acordes (una sección de un solo acorde
  no prueba nada).

Cifra plana (una sola sección sin repeticiones, p. ej. "No voy en tren"): no hay ciclo que buscar,
así que la lista se trata como el vocabulario de la canción (`coincide_vocabulario`): la sección
coincide si al menos UMBRAL de sus acordes distintos están en la lista y tiene 2 o más.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from guitarra_worker.domain.alignment import SEMITONES, parse_chord

UMBRAL = 0.75
MIN_PATRON = 3

Norm = tuple[int, bool]  # (raíz, es_menor)


def normalizar(label: str, shift: int = 0) -> Norm | None:
    """None para N.C. o ilegibles. `shift` suma semitonos (capo de la cifra)."""
    chord = parse_chord(label)
    if chord is None:
        return None
    quality = chord.quality
    menor = quality.startswith(("m", "dim")) and not quality.startswith("maj")
    return (chord.root + shift) % SEMITONES, menor


def sin_repetidos(seq: Sequence[Norm]) -> list[Norm]:
    return [x for i, x in enumerate(seq) if i == 0 or x != seq[i - 1]]


def flujo(labels: Sequence[str], shift: int = 0) -> list[Norm]:
    """Acordes normalizados, sin ilegibles y sin repetidos seguidos."""
    normalized = (normalizar(label, shift) for label in labels)
    return sin_repetidos([n for n in normalized if n is not None])


def ciclo_minimo(seq: Sequence[Norm]) -> list[Norm]:
    for period in range(1, len(seq) + 1):
        if all(seq[i] == seq[i % period] for i in range(len(seq))):
            return list(seq[:period])
    return list(seq)


def distancia_semiglobal(patron: Sequence[Norm], texto: Sequence[Norm]) -> int:
    """Distancia de edición mínima entre `patron` y cualquier tramo de `texto`."""
    previous = [0] * (len(texto) + 1)
    for i, p in enumerate(patron, 1):
        current = [i]
        for j, t in enumerate(texto, 1):
            cost = 0 if p == t else 1
            current.append(min(previous[j - 1] + cost, previous[j] + 1, current[j - 1] + 1))
        previous = current
    return min(previous)


def _repetir(ciclo: Sequence[Norm], largo: int) -> list[Norm]:
    veces = -(-largo // len(ciclo)) + 1
    return list(ciclo) * veces


def puntaje(seccion: Sequence[Norm], ciclo: Sequence[Norm]) -> float:
    """El más corto de los dos dentro del más largo (el ciclo se repite)."""
    if not seccion or not ciclo:
        return 0.0
    if len(seccion) <= len(ciclo):
        patron, texto = seccion, _repetir(ciclo, len(seccion))
    else:
        patron, texto = ciclo, seccion
    return max(0.0, 1.0 - distancia_semiglobal(patron, texto) / len(patron))


def pureza(seccion: Sequence[Norm], ciclo: Sequence[Norm]) -> float:
    if not seccion:
        return 0.0
    conocidos = set(ciclo)
    return sum(1 for c in seccion if c in conocidos) / len(seccion)


@dataclass(frozen=True)
class Veredicto:
    coincide: bool
    puntaje: float
    pureza: float
    referencia: str | None  # nombre de la sección de la referencia con la que mejor encaja


def _compara(seccion: Sequence[Norm], ciclo: Sequence[Norm]) -> tuple[bool, float, float]:
    patron = min(len(seccion), len(ciclo))
    score, purity = puntaje(seccion, ciclo), pureza(seccion, ciclo)
    ok = patron >= min(len(ciclo), MIN_PATRON) and score >= UMBRAL and purity >= UMBRAL
    return ok, score, purity


def mejor_referencia(
    seccion: Sequence[Norm], referencia: Sequence[tuple[str, list[Norm]]]
) -> Veredicto:
    """La mejor sección de la referencia para una sección del chart (ciclos ya reducidos)."""
    best = Veredicto(False, 0.0, 0.0, None)
    for name, ciclo in referencia:
        ok, score, purity = _compara(seccion, ciclo)
        candidate = Veredicto(ok, score, purity, name)
        if (candidate.coincide, score * purity) > (best.coincide, best.puntaje * best.pureza):
            best = candidate
    return best


def cobertura(flujo_chart: Sequence[Norm], ciclo: Sequence[Norm]) -> bool:
    """La sección de la referencia aparece en el flujo de toda la canción (puntaje >= UMBRAL)."""
    if not ciclo:
        return False
    return 1.0 - distancia_semiglobal(ciclo, flujo_chart) / len(ciclo) >= UMBRAL


def coincide_vocabulario(seccion: Sequence[Norm], vocabulario: Sequence[Norm]) -> Veredicto:
    """Para cifras planas: pureza respecto del conjunto de acordes de la cifra."""
    purity = pureza(seccion, vocabulario)
    ok = len(set(seccion)) >= 2 and purity >= UMBRAL
    return Veredicto(ok, 1.0 if ok else 0.0, purity, None)


def cobertura_vocabulario(flujo_chart: Sequence[Norm], vocabulario: Sequence[Norm]) -> float:
    """Qué parte de los acordes distintos de la cifra aparece en la canción detectada."""
    distintos = set(vocabulario)
    return len(distintos & set(flujo_chart)) / len(distintos) if distintos else 0.0
