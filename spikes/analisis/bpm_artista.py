"""Busca una canción en la página de artista de songbpm.com y muestra su BPM. Uso: bpm_artista.py <artista> <fragmento>"""

import re
import sys
import urllib.request

artista, fragmento = sys.argv[1], sys.argv[2].lower()
req = urllib.request.Request(
    f"https://songbpm.com/@{artista}", headers={"User-Agent": "Mozilla/5.0"}
)
pagina = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
for bloque in pagina.split('href="/@')[1:]:
    texto = re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"<[^>]+>", " | ", bloque[:900]))
    if fragmento in texto.lower()[:200]:
        print(texto[:200])
