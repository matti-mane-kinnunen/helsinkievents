"""Generic iCalendar (.ics) feed source. Recurring events are expanded."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import icalendar
import recurring_ical_events

from .. import http
from ..model import Event
from ..text import summarize

log = logging.getLogger(__name__)


def parse(text: str | bytes, source_name: str, start: date, end: date,
          summary_len: int = 220, default_place: str = "") -> list[Event]:
    cal = icalendar.Calendar.from_ical(text)
    out: list[Event] = []
    for comp in recurring_ical_events.of(cal).between(start, end + timedelta(days=1)):
        title = str(comp.get("SUMMARY", "")).strip()
        dtstart = comp.get("DTSTART")
        if not title or dtstart is None:
            continue
        s = dtstart.dt
        e = comp.get("DTEND").dt if comp.get("DTEND") is not None else None
        all_day = not isinstance(s, datetime)
        if all_day and isinstance(e, date) and not isinstance(e, datetime):
            e = e - timedelta(days=1)  # DTEND is exclusive for all-day events
            e = None if e <= s else datetime(e.year, e.month, e.day, 23, 59)
        status = str(comp.get("STATUS", "")).upper()
        loc = str(comp.get("LOCATION", "") or default_place)
        place, _, address = loc.partition(",")
        out.append(Event(
            title=title,
            start=s,
            end=e,
            all_day=all_day,
            place=place.strip(),
            address=address.strip(),
            summary=summarize(str(comp.get("DESCRIPTION", "")), summary_len),
            url=str(comp.get("URL", "") or ""),
            status="cancelled" if status == "CANCELLED" else "scheduled",
            source=source_name,
            source_id=str(comp.get("UID", "")),
        ))
    return out


def fetch(cfg: dict, start: date, end: date) -> list[Event]:
    name = cfg.get("name", "iCal")
    text = http.get(cfg["url"], accept="text/calendar")
    return parse(text, name, start, end, int(cfg.get("summary_length", 220)),
                 cfg.get("default_place", ""))
