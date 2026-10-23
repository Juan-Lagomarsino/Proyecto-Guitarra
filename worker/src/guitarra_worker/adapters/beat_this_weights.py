"""Pesos de beat_this (`final0`): bajada con reintentos y plan B con el espejo safetensors.

El host oficial (cloud.cp.jku.at) devolvió 503 durante el spike (ADR 0006). El espejo trae
safetensors sin los buffers `rotary_embed.freqs` (deterministas), que se completan desde un modelo
recién construido para armar el `.ckpt` que espera la librería.

Uso (lo llama scripts/install.ps1): `python -m guitarra_worker.adapters.beat_this_weights`.
"""

import hashlib
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from guitarra_worker.config import Settings

DOWNLOAD_ATTEMPTS = 3
RETRY_WAIT_S = 5.0
HTTP_TIMEOUT_S = 60.0
CHUNK_BYTES = 1 << 20

Downloader = Callable[[str, Path], None]
Converter = Callable[[Path, Path], None]


def download_file(url: str, dest: Path) -> None:
    """Baja `url` a `dest` por un archivo parcial, así un corte no deja un archivo a medias."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=HTTP_TIMEOUT_S) as response:
        response.raise_for_status()
        with partial.open("wb") as out:
            for chunk in response.iter_bytes():
                out.write(chunk)
    partial.replace(dest)


def _expected_state_keys() -> set[str]:
    from beat_this.model.beat_tracker import BeatThis

    return {f"model.{key}" for key in BeatThis().state_dict()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_expected_structure(path: Path) -> bool:
    """Carga con torch (solo tensores) y compara las claves del state_dict con las del modelo."""
    try:
        import torch

        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        return set(checkpoint["state_dict"]) == _expected_state_keys()
    except Exception:  # noqa: BLE001 - cualquier fallo de carga significa "no es un checkpoint"
        return False


def is_valid_checkpoint(path: Path, expected_sha256: str) -> bool:
    """Válido si el SHA-256 coincide con el oficial o, si no (el `.ckpt` convertido del espejo no
    es idéntico byte a byte), si carga y trae exactamente las claves del modelo."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if _sha256(path) == expected_sha256.lower():
        return True
    return _has_expected_structure(path)


def safetensors_to_ckpt(source: Path, dest: Path) -> None:
    """Arma el `.ckpt` a un archivo parcial y lo mueve al final: un corte no deja basura en dest."""
    import torch
    from beat_this.model.beat_tracker import BeatThis
    from safetensors.torch import load_file

    loaded = load_file(str(source))
    complete = BeatThis().state_dict()
    unexpected = set(loaded) - set(complete)
    if unexpected:
        raise ValueError(f"El espejo trae pesos que el modelo no conoce: {sorted(unexpected)}")
    complete.update(loaded)
    state = {f"model.{key}": value for key, value in complete.items()}
    partial = dest.with_suffix(dest.suffix + ".part")
    try:
        torch.save({"hyper_parameters": {}, "state_dict": state}, partial)
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)


def _try_download(
    url: str, dest: Path, download: Downloader, attempts: int, wait_s: float, sleep: Callable
) -> bool:
    for attempt in range(1, attempts + 1):
        try:
            download(url, dest)
            return True
        except (httpx.HTTPError, OSError) as error:
            print(f"Falló la bajada ({attempt}/{attempts}) de {url}: {error}", file=sys.stderr)
            if attempt < attempts:
                sleep(wait_s)
    return False


def _staging(dest: Path) -> Path:
    return dest.with_name(dest.name + ".part")


def _fetch_official(settings: Settings, dest: Path, download: Downloader, sleep: Callable) -> bool:
    """Baja, verifica y recién entonces mueve a `dest`. Una respuesta 200 basura se reintenta."""
    staging = _staging(dest)
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        staging.unlink(missing_ok=True)
        if _try_download(settings.beat_this_url, staging, download, 1, 0, sleep) and (
            is_valid_checkpoint(staging, settings.beat_this_sha256)
        ):
            staging.replace(dest)
            return True
        staging.unlink(missing_ok=True)
        print(f"Bajada oficial inválida ({attempt}/{DOWNLOAD_ATTEMPTS})", file=sys.stderr)
        if attempt < DOWNLOAD_ATTEMPTS:
            sleep(RETRY_WAIT_S)
    return False


def _fetch_mirror(
    settings: Settings, dest: Path, download: Downloader, convert: Converter, sleep: Callable
) -> bool:
    safetensors = dest.with_suffix(".safetensors")
    staging = _staging(dest)
    try:
        url = settings.beat_this_mirror_url
        if not _try_download(url, safetensors, download, DOWNLOAD_ATTEMPTS, RETRY_WAIT_S, sleep):
            return False
        convert(safetensors, staging)
        if not is_valid_checkpoint(staging, settings.beat_this_sha256):
            print("El checkpoint convertido del espejo no es válido.", file=sys.stderr)
            return False
        staging.replace(dest)
        return True
    except Exception as error:  # noqa: BLE001 - un espejo roto no tiene que tirar el instalador
        print(f"Falló la conversión del espejo: {error}", file=sys.stderr)
        return False
    finally:
        safetensors.unlink(missing_ok=True)
        staging.unlink(missing_ok=True)


def ensure_checkpoint(
    settings: Settings,
    download: Downloader = download_file,
    convert: Converter = safetensors_to_ckpt,
    sleep: Callable[[float], None] = time.sleep,
) -> Path:
    """Deja un checkpoint válido en `beat_this_checkpoint_path` (idempotente). Falla si no puede."""
    dest = settings.beat_this_checkpoint_path
    if is_valid_checkpoint(dest, settings.beat_this_sha256):
        return dest
    dest.unlink(missing_ok=True)
    if _fetch_official(settings, dest, download, sleep):
        return dest
    print("Host oficial caído o inválido; pruebo el espejo safetensors.", file=sys.stderr)
    if _fetch_mirror(settings, dest, download, convert, sleep):
        return dest
    raise RuntimeError(
        f"No pude bajar pesos válidos de beat_this ni del host oficial ni del espejo; dest={dest}"
    )


def main() -> int:
    try:
        path = ensure_checkpoint(Settings())
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Pesos de beat_this listos: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
