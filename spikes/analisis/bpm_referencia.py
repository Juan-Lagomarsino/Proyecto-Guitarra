"""Lee de songbpm.com el BPM, tonalidad y duración públicos de cada canción (pocos pedidos, con pausa)."""

import re
import time
import urllib.request

CANDIDATAS = {
    "flaca": "@andres-calamaro/flaca",
    "de-musica-ligera": "@soda-stereo/de-musica-ligera",
    "boys-dont-cry": "@the-cure/boys-dont-cry-xxlrk",
    "cerca-del-fuego": "@la-barranca/cerca-del-fuego-i6vum",
    "no-voy-en-tren": "@charly-garcia/no-voy-en-tren",
}


def pedir(ruta: str) -> str:
    req = urllib.request.Request(
        f"https://songbpm.com/{ruta}", headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return f"ERROR {e}"


def resumir(pagina: str) -> str:
    texto = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", pagina))
    frases = re.findall(r"[^.]{0,80}\bBPM\b[^.]{0,120}\.", texto)
    return " || ".join(frases[:3]) or texto[:200]


if __name__ == "__main__":
    for slug, ruta in CANDIDATAS.items():
        print(slug, "->", resumir(pedir(ruta)))
        time.sleep(2)
