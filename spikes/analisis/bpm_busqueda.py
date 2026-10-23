"""Usa el buscador de songbpm.com (el mismo formulario del sitio). Uso: bpm_busqueda.py "<consulta>" """

import re
import sys
import urllib.parse
import urllib.request

datos = urllib.parse.urlencode({"query": sys.argv[1]}).encode()
req = urllib.request.Request(
    "https://songbpm.com/searches", data=datos, headers={"User-Agent": "Mozilla/5.0"}
)
pagina = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
for bloque in pagina.split('href="/@')[1:12]:
    texto = re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"<[^>]+>", " | ", bloque[:900]))
    print(bloque.split('"')[0], "::", texto[:160])
