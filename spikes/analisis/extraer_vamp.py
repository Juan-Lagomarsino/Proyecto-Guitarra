"""Extrae los DLL de plugins Vamp embebidos (sin comprimir) en el instalador del Vamp Plugin Pack.

El instalador es solo GUI; esto evita instalarlo en el sistema. Uso:
    python extraer_vamp.py <Vamp.Plugin.Pack.Installer.exe> <directorio de salida>
"""

import struct
import sys
from pathlib import Path

DOS_STUB = b"MZ\x90\x00"


def tamanio_pe(datos: bytes, inicio: int) -> int | None:
    """Tamaño de un PE embebido a partir de su tabla de secciones."""
    try:
        e_lfanew = struct.unpack_from("<I", datos, inicio + 0x3C)[0]
        pe = inicio + e_lfanew
        if datos[pe : pe + 4] != b"PE\x00\x00":
            return None
        n_secciones = struct.unpack_from("<H", datos, pe + 6)[0]
        tam_opt = struct.unpack_from("<H", datos, pe + 20)[0]
        tabla = pe + 24 + tam_opt
        fin = 0
        for i in range(n_secciones):
            tam, ptr = struct.unpack_from("<II", datos, tabla + 40 * i + 16)
            fin = max(fin, ptr + tam)
        return fin or None
    except struct.error:
        return None


def es_x64(binario: bytes) -> bool:
    e_lfanew = struct.unpack_from("<I", binario, 0x3C)[0]
    return struct.unpack_from("<H", binario, e_lfanew + 4)[0] == 0x8664


def pes_embebidos(datos: bytes):
    pos = datos.find(DOS_STUB, 1)
    while pos != -1:
        tam = tamanio_pe(datos, pos)
        if tam:
            binario = datos[pos : pos + tam]
            if b"vampGetPluginDescriptor" in binario and es_x64(binario):
                yield binario
        pos = datos.find(DOS_STUB, pos + 1)


def nombre_de(binario: bytes) -> str:
    for nombre in (
        b"nnls-chroma",
        b"segmentino",
        b"qm-vamp-plugins",
        b"pyin",
        b"beatroot-vamp",
    ):
        if nombre in binario:
            return nombre.decode()
    return f"plugin-{len(binario)}"


if __name__ == "__main__":
    datos = Path(sys.argv[1]).read_bytes()
    destino = Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    for binario in pes_embebidos(datos):
        ruta = destino / f"{nombre_de(binario)}-{len(binario)}.dll"
        ruta.write_bytes(binario)
        print(ruta, len(binario))
