"""Convierte el HTML crudo de Cifra Club en la fixture JSON de referencia (spike; el parser de producción es F2-T10)."""

import html
import json
import re
import sys
from pathlib import Path

from songs import SONGS

FIXTURES = (
    Path(__file__).resolve().parents[2] / "worker" / "tests" / "fixtures" / "cifraclub"
)
SECCION = re.compile(r"^\s*\[([^\]]+)\]")
ACORDE = re.compile(r"<b>([^<]+)</b>")


def texto(fragmento: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).strip()


def extraer_pre(pagina: str) -> str:
    m = re.search(r"<pre[^>]*>(.*?)</pre>", pagina, re.DOTALL)
    if not m:
        raise ValueError("no hay <pre> con la cifra")
    return m.group(1)


def extraer_secciones(pre: str) -> list[dict]:
    secciones: list[dict] = []
    actual = {"name": "(sin título)", "chords": []}
    for linea in pre.splitlines():
        m = SECCION.match(linea)
        if m:
            if actual["chords"]:
                secciones.append(actual)
            actual = {"name": m.group(1).strip(), "chords": []}
            linea = linea[m.end() :]
        actual["chords"] += [html.unescape(c).strip() for c in ACORDE.findall(linea)]
    if actual["chords"]:
        secciones.append(actual)
    return secciones


def extraer_meta(pagina: str) -> dict:
    tom = re.search(r'id="cifra_tom">(.*?)</span>', pagina, re.DOTALL)
    capo = re.search(r'id="cifra_capo">(.*?)</span>', pagina, re.DOTALL)
    tom_txt = (
        re.sub(r"^tom:\s*", "", texto(tom.group(1)), flags=re.IGNORECASE).strip()
        if tom
        else ""
    )
    capo_txt = texto(capo.group(1)) if capo else ""
    m = re.search(r"(\d+)", capo_txt)
    return {
        "tonalidad": tom_txt or None,
        "capo": int(m.group(1)) if m else 0,
        "capo_texto": capo_txt,
    }


# Cifra Club responde 403 a pedidos automáticos; el HTML sale de copias del Internet Archive.
SNAPSHOTS = {
    "flaca": "https://web.archive.org/web/20251116070315/https://www.cifraclub.com.br/andres-calamaro/flaca/",
    "de-musica-ligera": "https://web.archive.org/web/20251207120244/https://www.cifraclub.com.br/soda-stereo/de-musica-ligera/",
    "boys-dont-cry": "https://web.archive.org/web/20250906114824/https://www.cifraclub.com.br/the-cure/boys-dont-cry/",
    "no-voy-en-tren": "https://web.archive.org/web/20160416001816/http://www.cifraclub.com.br/charly-garcia/no-voy-en-tren/",
}


def convertir(slug: str) -> dict:
    datos = SONGS[slug]
    pagina = (FIXTURES / "html" / f"{slug}.html").read_text(
        encoding="utf-8", errors="replace"
    )
    return {
        "title": datos["title"],
        "artist": datos["artist"],
        "url": f"https://www.cifraclub.com.br/{datos['cifraclub']}/",
        "snapshot": SNAPSHOTS.get(slug),
        **extraer_meta(pagina),
        "sections": extraer_secciones(extraer_pre(pagina)),
    }


if __name__ == "__main__":
    for slug in sys.argv[1:] or SONGS:
        if not (FIXTURES / "html" / f"{slug}.html").exists():
            print("sin HTML:", slug)
            continue
        ficha = convertir(slug)
        (FIXTURES / f"{slug}.json").write_text(
            json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            slug,
            ficha["tonalidad"],
            ficha["capo"],
            [(s["name"], len(s["chords"])) for s in ficha["sections"]],
        )
