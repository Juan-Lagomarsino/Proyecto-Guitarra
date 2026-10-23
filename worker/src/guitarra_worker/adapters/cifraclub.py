"""Adaptador de Cifra Club: arma la URL por artista y título, baja la página y la parsea.

Cualquier falla (red, 403, 404, HTML que cambió) da `None`: es un dato opcional y el
pipeline sigue sin él. Entre pedido y pedido espera `min_interval_s`.
"""

import html
import logging
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.cifraclub.com"
USER_AGENT = "Mozilla/5.0 (compatible; GuitarraPracticaWorker/0.1; uso personal)"

_PRE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.S)
_SECTION = re.compile(r"^\s*\[([^\]]+)\]")
_BOLD = re.compile(r"<b>([^<]+)</b>")
_CHORD_TEXT = re.compile(r"^[A-G][#b]?[^\s]*$")
_TAGS = re.compile(r"<[^>]+>")
_SPAN = r'<span[^>]*id="{id}"[^>]*>(.*?)</span>'
_DIGITS = re.compile(r"(\d+)")
_UNNAMED_SECTION = "(sin título)"


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


def slugify(text: str) -> str:
    """'Andrés Calamaro' -> 'andres-calamaro' (como arma las URLs Cifra Club)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_text = ascii_text.lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


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
    return [name for name in names if _CHORD_TEXT.match(name)]


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


class CifraClubClient:
    def __init__(
        self,
        http: httpx.Client,
        *,
        base_url: str = DEFAULT_BASE_URL,
        min_interval_s: float = 3.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._min_interval_s = min_interval_s
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None

    def fetch_chart(self, title: str | None, artist: str | None) -> CifraClubChart | None:
        if not title or not artist:
            return None
        url = f"{self._base_url}/{slugify(artist)}/{slugify(title)}/"
        page = self._get(url)
        chart = parse_cifraclub_html(page) if page else None
        return replace(chart, url=url) if chart else None

    def _get(self, url: str) -> str | None:
        self._wait_turn()
        try:
            response = self._http.get(
                url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=15.0
            )
        except httpx.HTTPError as exc:
            log.warning("Cifra Club no respondió (%s): %s", url, exc)
            return None
        if response.status_code != 200:
            log.info("Cifra Club respondió %s para %s", response.status_code, url)
            return None
        return response.text

    def _wait_turn(self) -> None:
        if self._last_request_at is not None:
            remaining = self._min_interval_s - (self._monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()
