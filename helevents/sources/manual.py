"""Manually added events: YAML files in events/manual/.

One file may contain a single event (mapping) or a list of events.

    title: Jazz-ilta
    start: 2026-11-14 19:00        # or 2026-11-14 for an all-day event
    end: 2026-11-14 22:00          # optional
    place: Savoy-teatteri
    address: Kasarmikatu 46-48     # optional
    url: https://example.org       # optional
    summary: Lyhyt kuvaus.         # optional
    status: cancelled              # optional
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import yaml

from ..model import Event, to_local
from ..text import summarize

log = logging.getLogger(__name__)

REQUIRED = ("title", "start")
ALLOWED = {"title", "start", "end", "place", "address", "url", "summary", "status", "tags"}


class ManualEventError(ValueError):
    pass


def parse_when(v) -> tuple[datetime, bool]:
    """Return (datetime, all_day)."""
    if isinstance(v, datetime):
        return to_local(v), False
    if isinstance(v, date):
        return to_local(v), True
    s = str(v).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H.%M", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M",
                "%d.%m.%Y %H.%M"):
        try:
            return to_local(datetime.strptime(s, fmt)), False
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return to_local(datetime.strptime(s, fmt).date()), True
        except ValueError:
            pass
    raise ManualEventError(f"Unrecognised date/time: {v!r} (use YYYY-MM-DD HH:MM)")


def to_event(d: dict, source_name: str = "Lisätty käsin", origin: str = "") -> Event:
    if not isinstance(d, dict):
        raise ManualEventError(f"{origin}: event must be a mapping")
    missing = [k for k in REQUIRED if not d.get(k)]
    if missing:
        raise ManualEventError(f"{origin}: missing field(s): {', '.join(missing)}")
    unknown = set(d) - ALLOWED
    if unknown:
        raise ManualEventError(f"{origin}: unknown field(s): {', '.join(sorted(unknown))}")
    start, all_day = parse_when(d["start"])
    end = None
    if d.get("end"):
        end, end_all_day = parse_when(d["end"])
        if end_all_day:
            end = end.replace(hour=23, minute=59)
        if end < start:
            raise ManualEventError(f"{origin}: end is before start")
    status = str(d.get("status") or "scheduled").lower()
    if status not in ("scheduled", "cancelled", "postponed"):
        raise ManualEventError(f"{origin}: status must be scheduled/cancelled/postponed")
    return Event(
        title=str(d["title"]).strip(),
        start=start,
        end=end,
        all_day=all_day,
        place=str(d.get("place") or "").strip(),
        address=str(d.get("address") or "").strip(),
        summary=summarize(str(d.get("summary") or ""), 400),
        url=str(d.get("url") or "").strip(),
        status=status,
        source=source_name,
        source_id=origin,
        tags=list(d.get("tags") or []),
    )


def load_file(path: Path, source_name: str = "Lisätty käsin") -> list[Event]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    items = data if isinstance(data, list) else [data]
    return [to_event(d, source_name, f"{path.name}#{i}" if len(items) > 1 else path.name)
            for i, d in enumerate(items)]


def load_dir(directory: Path, source_name: str = "Lisätty käsin",
             strict: bool = False) -> tuple[list[Event], list[str]]:
    events, errors = [], []
    for path in sorted(directory.glob("*.y*ml")):
        try:
            events += load_file(path, source_name)
        except (ManualEventError, yaml.YAMLError) as e:
            errors.append(f"{path.name}: {e}")
    if strict and errors:
        raise ManualEventError("\n".join(errors))
    return events, errors


def fetch(cfg: dict, start: date, end: date) -> list[Event]:
    root = Path(cfg.get("_root", "."))
    events, errors = load_dir(root / cfg.get("path", "events/manual"),
                              cfg.get("name", "Lisätty käsin"))
    for e in errors:
        log.error("Manual event skipped: %s", e)
    return [e for e in events if e.end_date >= start and e.start_date <= end]
