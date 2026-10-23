"""Ajustes de la app (fila única): tema, tipografías, instrumento, afinación y zona horaria.

La lista de tokens debe ser exactamente la de `ui/src/theme/tokens.css`; un test las compara.
"""

import re
from typing import Annotated, Any, Literal, Self, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from guitarra_api.domain.notation import NUM_STRINGS, STANDARD_TUNING, NoteWithOctave

DEFAULT_TIMEZONE = "America/Montevideo"
Instrument = Literal["classical", "electric"]
INSTRUMENTS: tuple[str, ...] = get_args(Instrument)

# Tema por defecto: `:root` de docs/referencias/taller-electrica.html (ver tokens.css).
DEFAULT_THEME_TOKENS: dict[str, str] = {
    "--bg": "#14121f",
    "--surface": "#1f1c30",
    "--surface-2": "#262240",
    "--line": "#34304d",
    "--text": "#f3efe4",
    "--muted": "#9a95b3",
    "--accent": "#ffb534",
    "--accent-dim": "#7a5a22",
    "--accent-ink": "#1b1405",
    "--good": "#6fd39a",
    "--good-dim": "#1f4a35",
    "--wood": "#1a1729",
    "--note-tonic": "#ffb534",
    "--note-other": "#3a3558",
    "--note-active": "#f3efe4",
    "--string": "#9a95b3",
    "--fret": "#34304d",
}
DEFAULT_FONTS: dict[str, str] = {
    "--font-display": "'Anton', Impact, 'Arial Narrow', sans-serif",
    "--font-mono": "'IBM Plex Mono', ui-monospace, Menlo, monospace",
}
COLOR_TOKENS = tuple(DEFAULT_THEME_TOKENS)
FONT_TOKENS = tuple(DEFAULT_FONTS)

_HEX = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$", re.IGNORECASE)
_NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)"
_ARG = rf"{_NUM}(?:%|deg|grad|rad|turn)?"
_ALPHA = rf"{_NUM}%?"
# Sintaxis clásica (con comas) y moderna (espacios y "/" para el alfa).
_FUNCTION = re.compile(
    rf"^(?:rgba?|hsla?)\(\s*(?:"
    rf"{_ARG}\s*,\s*{_ARG}\s*,\s*{_ARG}(?:\s*,\s*{_ALPHA})?"
    rf"|{_ARG}\s+{_ARG}\s+{_ARG}(?:\s*/\s*{_ALPHA})?"
    rf")\s*\)$",
    re.IGNORECASE,
)
_NAMED_COLORS = frozenset(
    "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue "
    "blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk "
    "crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki "
    "darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen "
    "darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue "
    "dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite "
    "gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki "
    "lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan "
    "lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen "
    "lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen "
    "magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen "
    "mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream "
    "mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid "
    "palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum "
    "powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown "
    "seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen "
    "steelblue tan teal thistle tomato transparent turquoise violet wheat white whitesmoke "
    "yellow yellowgreen".split()
)
_FORBIDDEN_FONT_CHARS = re.compile(r"[;{}<>\\\n\r]|/\*|url\(", re.IGNORECASE)


def is_css_color(value: str) -> bool:
    """Hex (#rgb, #rgba, #rrggbb, #rrggbbaa), rgb/rgba/hsl/hsla y nombres CSS."""
    text = value.strip()
    return bool(_HEX.match(text) or _FUNCTION.match(text) or text.lower() in _NAMED_COLORS)


def is_font_family(value: str) -> bool:
    return bool(value.strip()) and not _FORBIDDEN_FONT_CHARS.search(value)


def is_iana_timezone(value: str) -> bool:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def _check_exact_keys(label: str, values: dict[str, str], expected: tuple[str, ...]) -> None:
    missing = [key for key in expected if key not in values]
    unknown = [key for key in values if key not in expected]
    if missing or unknown:
        raise ValueError(f"{label}: faltan {missing} y sobran {unknown}")


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str = DEFAULT_TIMEZONE
    theme_tokens: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_THEME_TOKENS))
    fonts: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_FONTS))
    default_instrument: Instrument = "electric"
    tuning: Annotated[
        list[NoteWithOctave], Field(min_length=NUM_STRINGS, max_length=NUM_STRINGS)
    ] = Field(default_factory=lambda: list(STANDARD_TUNING))

    @field_validator("timezone")
    @classmethod
    def _timezone_is_iana(cls, value: str) -> str:
        if not is_iana_timezone(value):
            raise ValueError(f"Zona horaria IANA inválida: {value!r}")
        return value

    @model_validator(mode="after")
    def _theme_is_complete_and_valid(self) -> Self:
        _check_exact_keys("theme_tokens", self.theme_tokens, COLOR_TOKENS)
        _check_exact_keys("fonts", self.fonts, FONT_TOKENS)
        for token, color in self.theme_tokens.items():
            if not is_css_color(color):
                raise ValueError(f"{token}: color CSS inválido: {color!r}")
        for token, font in self.fonts.items():
            if not is_font_family(font):
                raise ValueError(f"{token}: tipografía inválida: {font!r}")
        return self


def _repaired(stored: Any, defaults: dict[str, str], is_valid: Any) -> dict[str, str]:
    """Una entrada por token conocido: el valor guardado si es válido, si no el default."""
    source = stored if isinstance(stored, dict) else {}
    repaired = {}
    for key, default in defaults.items():
        value = source.get(key)
        repaired[key] = value if isinstance(value, str) and is_valid(value) else default
    return repaired


def settings_from_stored(
    timezone: Any, theme_tokens: Any, fonts: Any, default_instrument: Any, tuning: Any
) -> AppSettings:
    """Lee valores guardados tolerando filas incompletas o viejas: lo faltante o inválido
    se reemplaza por su default y las claves desconocidas se descartan."""
    defaults = default_app_settings().model_dump()
    scalars = {"timezone": timezone, "default_instrument": default_instrument, "tuning": tuning}
    valid = {}
    for name, value in scalars.items():
        try:
            candidate = AppSettings.model_validate({**defaults, name: value})
            valid[name] = getattr(candidate, name)
        except ValueError:
            valid[name] = defaults[name]
    return AppSettings(
        theme_tokens=_repaired(theme_tokens, DEFAULT_THEME_TOKENS, is_css_color),
        fonts=_repaired(fonts, DEFAULT_FONTS, is_font_family),
        **valid,
    )


def default_app_settings() -> AppSettings:
    return AppSettings()
