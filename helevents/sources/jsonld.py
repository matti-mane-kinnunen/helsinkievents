"""Scrape schema.org/Event JSON-LD blocks from ordinary web pages.

Many venue and ticketing sites embed
<script type="application/ld+json">{"@type": "Event", ...}</script>
for search engines. This source reads those, so most "netpages" can be
added with just a URL and no custom scraper.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from html.parser import HTMLParser

from .. import http
from ..model import Event, to_local
from ..text import summarize

log = logging.getLogger(__name__)

EVENT_TYPES = {"Event", "MusicEvent", "TheaterEvent", "DanceEvent", "ComedyEvent",
               "ExhibitionEvent", "ScreeningEvent", "Festival", "LiteraryEvent",
               "SocialEvent", "ChildrensEvent", "EducationEvent", "SportsEvent",
               "FoodEvent", "VisualArtsEvent"}


class _LdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks: list[str] = []
        self._in = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._in, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "script" and self._in:
            self.blocks.append("".join(self._buf))
            self._in = False

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        t = node.get("@type")
        types = set(t) if isinstance(t, list) else {t}
        if types & EVENT_TYPES:
            yield node
        for key in ("@graph", "subEvent", "itemListElement", "item", "event"):
            if key in node:
                yield from _walk(node[key])


def _dt(s) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        if len(s) == 10:
            return to_local(date.fromisoformat(s))
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(v) -> str:
    if isinstance(v, list):
        v = v[0] if v else ""
    if isinstance(v, dict):
        v = v.get("name") or v.get("@value") or ""
    return str(v or "")


def parse(html_text: str, source_name: str, page_url: str = "",
          summary_len: int = 220) -> list[Event]:
    p = _LdParser()
    p.feed(html_text)
    out: list[Event] = []
    for block in p.blocks:
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            log.debug("Invalid JSON-LD block on %s", page_url)
            continue
        for node in _walk(data):
            start = _dt(node.get("startDate"))
            title = _text(node.get("name")).strip()
            if not start or not title:
                continue
            loc = node.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            place, address = "", ""
            if isinstance(loc, dict):
                place = _text(loc.get("name"))
                addr = loc.get("address")
                if isinstance(addr, dict):
                    address = ", ".join(x for x in (_text(addr.get("streetAddress")),
                                                    _text(addr.get("addressLocality"))) if x)
                elif addr:
                    address = _text(addr)
            elif isinstance(loc, str):
                place = loc
            status = _text(node.get("eventStatus"))
            out.append(Event(
                title=title,
                start=start,
                end=_dt(node.get("endDate")),
                all_day=len(str(node.get("startDate"))) == 10,
                place=place,
                address=address,
                summary=summarize(_text(node.get("description")), summary_len),
                url=_text(node.get("url")) or page_url,
                status="cancelled" if "Cancelled" in status else
                       "postponed" if "Postponed" in status else "scheduled",
                source=source_name,
            ))
    return out


def fetch(cfg: dict, start: date, end: date) -> list[Event]:
    name = cfg.get("name", "Web")
    urls = cfg.get("urls") or ([cfg["url"]] if cfg.get("url") else [])
    events: list[Event] = []
    for url in urls:
        try:
            events += parse(http.get_text(url, accept="text/html"), name, url,
                            int(cfg.get("summary_length", 220)))
        except Exception as e:  # one bad page must not kill the source
            log.warning("%s: %s failed: %s", name, url, e)
    if cfg.get("default_place"):
        for ev in events:
            ev.place = ev.place or cfg["default_place"]
    return [e for e in events if e.end_date >= start and e.start_date <= end]
