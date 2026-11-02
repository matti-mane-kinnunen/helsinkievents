"""Text helpers: HTML stripping and summary trimming."""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from .model import clean_ws


class _Stripper(HTMLParser):
    BLOCK = {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    if "<" not in s:
        return clean_ws(html.unescape(s))
    p = _Stripper()
    p.feed(s)
    p.close()
    return clean_ws("".join(p.parts))


_sentence_end = re.compile(r"[.!?…](?=\s|$)")


def summarize(text: str | None, limit: int = 220) -> str:
    """Trim text to at most `limit` chars, preferring a sentence boundary."""
    t = strip_html(text)
    if len(t) <= limit:
        return t
    cut = t[:limit]
    ends = [m.end() for m in _sentence_end.finditer(cut)]
    if ends and ends[-1] >= limit * 0.5:
        return cut[: ends[-1]].strip()
    sp = cut.rfind(" ")
    if sp > limit * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:-–") + "…"
