"""Parser de la cifra de Cifra Club que Juan Pedro pega a mano (ADR 0012).

Acepta texto plano (copiado de la página: `[Intro]`, líneas de acordes, `Tom:`, capo) o el HTML
de la página. Sin cifra reconocible da `None`: es un dato opcional y el pipeline sigue sin él.
No hace ningún pedido de red.
"""

import html
import re
from dataclasses import dataclass, field

_PRE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.S)
_SECTION = re.compile(r"^\s*\[([^\]]+)\]")
_BOLD = re.compile(r"<b>([^<]+)</b>")
_CHORD_TEXT = re.compile(r"^[A-G][#b]?[^\s]*$")
_TAGS = re.compile(r"<[^>]+>")
_SPAN = r'<span[^>]*id="{id}"[^>]*>(.*?)</span>'
_DIGITS = re.compile(r"(\d+)")
_UNNAMED_SECTION = ""  # sin encabezado: el armado usa el nombre detectado

_CHORD_TOKEN = re.compile(
    r"^[A-G][#b]?(?:maj|min|dim|aug|sus|add|m|M|[°º+\-]|[#b]|\d|[(),])*(?:/(?:[A-G][#b]?)?)?$"
)
_IGNORABLE_TOKEN = re.compile(r"^(?:\(?(?:\d+x|x\d+)\)?|[|\-/%]+|N\.?C\.?)$", re.I)
_TEXT_KEY = re.compile(r"^\s*tom\s*:\s*(\S+)", re.I | re.M)
_TEXT_CAPO = re.compile(r"^\s*capo(?:traste)?\b[^\d\n]{0,20}(\d{1,2})", re.I | re.M)


@dataclass
class CifraClubSection:
    name: str
    chords: list[str]


@dataclass
class CifraClubChart:
    sections: list[CifraClubSection] = field(default_factory=list)
    capo: int = 0
    key: str | None = None
    url: str = ""

    def all_chords(self) -> list[str]:
        return [chord for section in self.sections for chord in section.chords]


def _plain_text(fragment: str) -> str:
    return html.unescape(_TAGS.sub(" ", fragment)).strip()


def _span_text(page: str, span_id: str) -> str:
    match = re.search(_SPAN.format(id=span_id), page, re.S)
    return _plain_text(match.group(1)) if match else ""


def _parse_capo(page: str) -> int:
    match = _DIGITS.search(_span_text(page, "cifra_capo"))
    return int(match.group(1)) if match else 0


def _parse_key(page: str) -> str | None:
    text = re.sub(r"^tom:\s*", "", _span_text(page, "cifra_tom"), flags=re.I).strip()
    return text or None


def _line_chords(line: str) -> list[str]:
    names = (html.unescape(raw).strip() for raw in _BOLD.findall(line))
    return [name.removesuffix("/") for name in names if _CHORD_TEXT.match(name)]


def _is_tab(section_name: str) -> bool:
    return section_name.strip().lower().startswith("tab")


def _parse_sections(pre: str) -> list[CifraClubSection]:
    sections: list[CifraClubSection] = []
    name, chords, in_tab = _UNNAMED_SECTION, [], False
    for line in pre.splitlines():
        header = _SECTION.match(line)
        if header:
            if chords:
                sections.append(CifraClubSection(name, chords))
            name, chords = html.unescape(header.group(1)).strip(), []
            in_tab = _is_tab(name)
            line = line[header.end() :]
        if not in_tab:
            chords += _line_chords(line)
    if chords:
        sections.append(CifraClubSection(name, chords))
    return sections


def parse_cifraclub_html(page: str) -> CifraClubChart | None:
    """None si la página no tiene el bloque de cifra o no se reconoce ningún acorde."""
    match = _PRE.search(page)
    if not match:
        return None
    sections = _parse_sections(match.group(1))
    if not sections:
        return None
    return CifraClubChart(sections, _parse_capo(page), _parse_key(page))


def _text_line_chords(line: str) -> list[str]:
    """Acordes de la línea si es una línea de acordes (todo acorde o marca ignorable), si no []."""
    tokens = line.split()
    chords = [t for t in tokens if _CHORD_TOKEN.match(t)]
    others = [t for t in tokens if t not in chords]
    if not chords or not all(_IGNORABLE_TOKEN.match(t) for t in others):
        return []
    return [chord.removesuffix("/") for chord in chords]  # "A/" es A: la barra no trae bajo


def _parse_text_sections(text: str) -> list[CifraClubSection]:
    sections: list[CifraClubSection] = []
    name, chords, in_tab = _UNNAMED_SECTION, [], False
    for line in text.splitlines():
        header = _SECTION.match(line)
        if header:
            if chords:
                sections.append(CifraClubSection(name, chords))
            name, chords = header.group(1).strip(), []
            in_tab = _is_tab(name)
            line = line[header.end() :]
        if not in_tab:
            chords += _text_line_chords(line)
    if chords:
        sections.append(CifraClubSection(name, chords))
    return sections


def _first_group(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def parse_cifraclub_plain_text(text: str) -> CifraClubChart | None:
    """None si el texto no tiene ninguna línea de acordes."""
    sections = _parse_text_sections(text)
    if not sections:
        return None
    capo = _first_group(_TEXT_CAPO, text)
    return CifraClubChart(sections, int(capo) if capo else 0, _first_group(_TEXT_KEY, text))


def parse_cifraclub_text(text: str | None) -> CifraClubChart | None:
    """Parsea lo que se pegó: HTML de la página si trae `<pre`, si no texto plano."""
    if not text or not text.strip():
        return None
    if "<pre" in text.lower():
        return parse_cifraclub_html(text)
    return parse_cifraclub_plain_text(text)
