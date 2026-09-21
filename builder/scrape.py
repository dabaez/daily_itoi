"""Scrape Itoi's 今日のダーリン from 1101.com.

Every source returns a Column with the column's own date (as printed on the page),
so the caller can tell whether a fallback gave it something newer than what it has.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

log = logging.getLogger(__name__)

PRIMARY_URL = "https://www.1101.com/m/recent/darling.html"
FALLBACK_URLS = [
    "https://www.1101.com/darling_column/yesterday.html",
    "https://www.1101.com/m/recent/yesterdays_darling.html",
]

USER_AGENT = "Mozilla/5.0 (compatible; todays-darling-earthbound/1.0; non-commercial fan tribute)"
TIMEOUT = 20
MIN_BODY_CHARS = 100  # anything shorter is almost certainly a broken parse


class ScrapeError(Exception):
    pass


@dataclass
class Column:
    date: str  # YYYY-MM-DD, as printed on the page
    title: str
    body: str  # paragraphs separated by blank lines
    source_url: str

    @property
    def text_ja(self) -> str:
        return f"{self.title}\n\n{self.body}"


def fetch(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    # The mobile pages are Shift_JIS; cp932 is the superset that actually decodes them
    # (e.g. ‥ and circled numbers). The desktop page declares utf-8.
    head = resp.content[:1024].lower()
    if b"shift_jis" in head or b"shift-jis" in head:
        return resp.content.decode("cp932", errors="replace")
    return resp.content.decode("utf-8", errors="replace")


def _text_with_breaks(node: Tag) -> str:
    """Flatten a node to text, turning <br> into newlines and keeping link text."""
    parts: list[str] = []
    for el in node.descendants:
        if isinstance(el, NavigableString):
            if el.parent is not None and el.parent.name in ("script", "style"):
                continue
            parts.append(str(el))
        elif isinstance(el, Tag) and el.name == "br":
            parts.append("\n")
    return "".join(parts)


def _clean_paragraphs(raw: str) -> list[str]:
    raw = raw.replace("\r", "")
    paras = []
    for block in re.split(r"\n\s*\n", raw):
        # Lines inside a paragraph are hard-wrapped for layout only; join them.
        text = "".join(line.strip() for line in block.split("\n"))
        text = text.replace("　", "").strip()
        if text:
            paras.append(text)
    return paras


def _finish(date: str, paras: list[str], url: str) -> Column:
    if len(paras) < 2:
        raise ScrapeError(f"{url}: expected a title and a body, got {len(paras)} paragraph(s)")
    title, body = paras[0], "\n\n".join(paras[1:])
    if len(body) < MIN_BODY_CHARS:
        raise ScrapeError(f"{url}: body suspiciously short ({len(body)} chars)")
    return Column(date=date, title=title, body=body, source_url=url)


def parse_mobile(html: str, url: str) -> Column:
    """The /m/recent/ pages: date in the yellow header, column in the padded div."""
    soup = BeautifulSoup(html, "html.parser")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", soup.find("table").get_text() if soup.find("table") else "")
    if not m:
        raise ScrapeError(f"{url}: no date found in header")
    container = soup.find("div", style=re.compile(r"padding"))
    if container is None:
        raise ScrapeError(f"{url}: column container not found")
    return _finish(m.group(1), _clean_paragraphs(_text_with_breaks(container)), url)


def parse_desktop_yesterday(html: str, url: str) -> Column:
    """The /darling_column/yesterday.html page: Alpine.js markup, title in an attribute."""
    soup = BeautifulSoup(html, "html.parser")
    body_tag = soup.find("body")
    m = re.search(r"dayjs\(`(\d{4}-\d{2}-\d{2})`\)", str(body_tag.get("x-data", "")) if body_tag else "")
    if not m:
        raise ScrapeError(f"{url}: no date found")
    darling = soup.find("div", class_="darling")
    text_div = soup.find("div", class_="darling-text")
    if darling is None or text_div is None:
        raise ScrapeError(f"{url}: column container not found")
    tm = re.search(r"darlingTitle:\s*`([^`]*)`", darling.get("x-data", ""))
    title = tm.group(1).strip() if tm else ""
    for s in text_div.find_all("span", class_=["pc_space", "sp_space"]):
        s.decompose()
    # The body is hard-wrapped with <br />; paragraphs are separated by <br class="br">.
    for br in text_div.find_all("br"):
        br.replace_with("\n\n" if "br" in (br.get("class") or []) else "")
    paras = _clean_paragraphs(text_div.get_text())
    if title:
        paras.insert(0, title)
    return _finish(m.group(1), paras, url)


PARSERS = {
    PRIMARY_URL: parse_mobile,
    FALLBACK_URLS[0]: parse_desktop_yesterday,
    FALLBACK_URLS[1]: parse_mobile,
}


def scrape(url: str) -> Column:
    return PARSERS[url](fetch(url), url)


def scrape_best() -> Column:
    """Primary first; fall back to the "yesterday" pages if it fails.

    Returns the first source that parses. Raises ScrapeError if none do.
    """
    errors = []
    for url in [PRIMARY_URL, *FALLBACK_URLS]:
        try:
            col = scrape(url)
            log.info("scraped %s (column date %s, %d chars)", url, col.date, len(col.body))
            return col
        except Exception as e:  # network, HTTP, or parse failure: try the next source
            log.warning("scrape failed for %s: %s", url, e)
            errors.append(f"{url}: {e}")
    raise ScrapeError("all sources failed:\n  " + "\n  ".join(errors))
