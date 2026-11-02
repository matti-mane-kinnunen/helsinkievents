"""City of Helsinki Linked Events API (https://api.hel.fi/linkedevents/v1/).

API docs: https://dev.hel.fi/apis/linkedevents
"""
from __future__ import annotations

import logging
import time
import urllib.parse
from datetime import date, datetime

from .. import http
from ..model import Event
from ..text import summarize

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.hel.fi/linkedevents/v1/event/"
LANGS = ("fi", "en", "sv")
STATUS = {
    "EventCancelled": "cancelled",
    "EventPostponed": "postponed",
    "EventRescheduled": "scheduled",
    "EventScheduled": "scheduled",
}


def pick(d, langs=LANGS) -> str:
    """Pick a translation from a {"fi": .., "en": ..} dict."""
    if not d:
        return ""
    if isinstance(d, str):
        return d
    for lang in langs:
        v = d.get(lang)
        if v:
            return v
    return next((v for v in d.values() if v), "")


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def build_url(cfg: dict, start: date, end: date) -> str:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "include": "location,keywords",
        "sort": "start_time",
        "page_size": str(cfg.get("page_size", 100)),
        # parent "recurring"/"umbrella" events are containers; keep only real instances
        "super_event_type": "none",
    }
    for k, v in (cfg.get("params") or {}).items():
        params[k] = ",".join(v) if isinstance(v, (list, tuple)) else str(v)
    return cfg.get("base_url", DEFAULT_BASE) + "?" + urllib.parse.urlencode(params, safe=":,/")


def keyword_ids(raw: dict) -> set[str]:
    out = set()
    for k in raw.get("keywords") or []:
        kid = k.get("id") or (k.get("@id", "").rstrip("/").rsplit("/", 1)[-1])
        if kid:
            out.add(kid)
    return out


def keyword_names(raw: dict) -> list[str]:
    return [pick(k.get("name")) for k in raw.get("keywords") or [] if k.get("name")]


def to_event(raw: dict, source_name: str, summary_len: int = 220) -> Event | None:
    if raw.get("super_event_type") in ("recurring", "umbrella"):
        return None
    if raw.get("deleted"):
        return None
    start = parse_dt(raw.get("start_time"))
    title = pick(raw.get("name")).strip()
    if not start or not title:
        return None
    loc = raw.get("location") or {}
    place = pick(loc.get("name"))
    address = ", ".join(
        x for x in (pick(loc.get("street_address")), pick(loc.get("address_locality"))) if x
    )
    if raw.get("location_extra_info"):
        extra = pick(raw["location_extra_info"])
        if extra and extra not in place:
            place = f"{place} ({extra})" if place else extra
    summary = summarize(
        pick(raw.get("short_description")) or pick(raw.get("description")), summary_len
    )
    url = pick(raw.get("info_url"))
    if not url and raw.get("id"):
        url = f"https://tapahtumat.hel.fi/fi/events/{raw['id']}"
    # Linked Events marks date-only events with has_start_time = False
    all_day = raw.get("has_start_time") is False
    end = parse_dt(raw.get("end_time"))
    return Event(
        title=title,
        start=start,
        end=end,
        all_day=all_day,
        place=place,
        address=address,
        summary=summary,
        url=url,
        status=STATUS.get(raw.get("event_status"), "scheduled"),
        source=source_name,
        source_id=raw.get("id", ""),
        tags=keyword_names(raw)[:6],
    )


def fetch(cfg: dict, start: date, end: date) -> list[Event]:
    name = cfg.get("name", "Linked Events")
    url: str | None = build_url(cfg, start, end)
    max_pages = int(cfg.get("max_pages", 60))
    exclude_kw = set(cfg.get("exclude_keywords") or [])
    summary_len = int(cfg.get("summary_length", 220))
    events: list[Event] = []
    pages = 0
    while url and pages < max_pages:
        data = http.get_json(url)
        pages += 1
        if pages == 1:
            log.info("%s: API reports %s events", name, data.get("meta", {}).get("count"))
        for raw in data.get("data", []):
            if exclude_kw and keyword_ids(raw) & exclude_kw:
                continue
            ev = to_event(raw, name, summary_len)
            if ev:
                events.append(ev)
        url = (data.get("meta") or {}).get("next")
        if url:
            time.sleep(float(cfg.get("delay", 0.3)))
    if url:
        log.warning("%s: stopped after max_pages=%d, more results exist", name, max_pages)
    return events
