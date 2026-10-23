import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from guitarra_api.domain.app_settings import (
    COLOR_TOKENS,
    DEFAULT_FONTS,
    DEFAULT_THEME_TOKENS,
    FONT_TOKENS,
    AppSettings,
    default_app_settings,
    is_css_color,
)

TOKENS_CSS = Path(__file__).resolve().parents[3] / "ui" / "src" / "theme" / "tokens.css"


@pytest.mark.parametrize(
    "value",
    [
        "#abc",
        "#ABCD",
        "#14121f",
        "#14121fcc",
        "rgb(20, 18, 31)",
        "rgba(20,18,31,0.5)",
        "rgb(20 18 31 / 50%)",
        "hsl(250, 26%, 10%)",
        "hsla(250, 26%, 10%, .4)",
        "hsl(250deg 26% 10%)",
        "transparent",
        "rebeccapurple",
        "RED",
    ],
)
def test_colores_validos(value: str) -> None:
    assert is_css_color(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "#ab",
        "#abcde",
        "#gggggg",
        "14121f",
        "rgb(1,2)",
        "rgb(a, b, c)",
        "rgb(1,2,3",
        "hsl(250, 26%)",
        "red; background: url(x)",
        "no-es-color",
        "var(--bg)",
        "#fff url(x)",
    ],
)
def test_colores_invalidos(value: str) -> None:
    assert not is_css_color(value)


def test_defaults_cubren_todos_los_tokens() -> None:
    assert set(DEFAULT_THEME_TOKENS) == set(COLOR_TOKENS)
    assert set(DEFAULT_FONTS) == set(FONT_TOKENS)
    assert all(is_css_color(value) for value in DEFAULT_THEME_TOKENS.values())


def test_lista_de_tokens_coincide_con_el_css_de_la_ui() -> None:
    css = TOKENS_CSS.read_text(encoding="utf-8")
    declared = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", css))
    ui_colors = {k: v.strip() for k, v in declared.items() if not k.startswith("--font-")}
    ui_fonts = {k for k in declared if k.startswith("--font-")}
    assert ui_colors == DEFAULT_THEME_TOKENS
    assert ui_fonts == set(FONT_TOKENS)


def test_defaults_de_app_settings() -> None:
    settings = default_app_settings()
    assert settings.timezone == "America/Montevideo"
    assert settings.default_instrument == "electric"
    assert settings.tuning == ["E2", "A2", "D3", "G3", "B3", "E4"]


def _payload(**overrides: object) -> dict[str, object]:
    return {**default_app_settings().model_dump(), **overrides}


def test_rechaza_token_faltante() -> None:
    tokens = dict(DEFAULT_THEME_TOKENS)
    del tokens["--bg"]
    with pytest.raises(ValidationError, match="--bg"):
        AppSettings.model_validate(_payload(theme_tokens=tokens))


def test_rechaza_token_desconocido() -> None:
    with pytest.raises(ValidationError, match="--inventado"):
        AppSettings.model_validate(
            _payload(theme_tokens={**DEFAULT_THEME_TOKENS, "--inventado": "#fff"})
        )


def test_rechaza_color_invalido() -> None:
    with pytest.raises(ValidationError, match="--accent"):
        AppSettings.model_validate(
            _payload(theme_tokens={**DEFAULT_THEME_TOKENS, "--accent": "naranjaaa"})
        )


def test_rechaza_tipografia_faltante_o_peligrosa() -> None:
    with pytest.raises(ValidationError):
        AppSettings.model_validate(_payload(fonts={"--font-display": "Anton"}))
    with pytest.raises(ValidationError):
        AppSettings.model_validate(
            _payload(fonts={**DEFAULT_FONTS, "--font-mono": "x; } body { color: red"})
        )
    with pytest.raises(ValidationError):
        AppSettings.model_validate(_payload(fonts={**DEFAULT_FONTS, "--font-mono": "  "}))


def test_rechaza_zona_horaria_inexistente() -> None:
    with pytest.raises(ValidationError, match="Mars/Base"):
        AppSettings.model_validate(_payload(timezone="Mars/Base"))


def test_acepta_otra_zona_horaria() -> None:
    assert AppSettings.model_validate(_payload(timezone="Europe/Madrid")).timezone == (
        "Europe/Madrid"
    )


def test_rechaza_instrumento_y_afinacion_invalidos() -> None:
    with pytest.raises(ValidationError):
        AppSettings.model_validate(_payload(default_instrument="banjo"))
    with pytest.raises(ValidationError):
        AppSettings.model_validate(_payload(tuning=["E2", "A2"]))
    with pytest.raises(ValidationError):
        AppSettings.model_validate(_payload(tuning=["E2", "A2", "D3", "G3", "B3", "X9"]))
