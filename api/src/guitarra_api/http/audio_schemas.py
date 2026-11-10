from typing import Literal

from pydantic import BaseModel, Field

AudioKind = Literal["original", "no_guitar", "stem"]  # = AUDIO_ASSET_KINDS (lo verifica un test)


class AudioAssetOut(BaseModel):
    kind: AudioKind
    format: str
    url: str = Field(description="Ruta de descarga; para <audio src> la UI le agrega ?token=")


class AudioUploadedOut(BaseModel):
    kind: AudioKind
    format: str
    size: int
