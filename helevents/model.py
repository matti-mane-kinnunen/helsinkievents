"""Normalised event model shared by all sources."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Helsinki")


@dataclass
class Event:
    title: str
    start: datetime                 # timezone-aware, Europe/Helsinki
    source: str                     # human readable source name
    end: datetime | None = None
    all_day: bool = False
    place: str = ""
    address: str = ""
    summary: str = ""
    url: str = ""
    status: str = "scheduled"       # scheduled | cancelled | postponed
    source_id: str = ""             # id in the original source, if any
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.start = to_local(self.start)
        if self.end is not None:
            self.end = to_local(self.end)
            if self.end < self.start:
                self.end = None

    # ------------------------------------------------------------------
    @property
    def start_date(self) -> date:
        return self.start.date()

    @property
    def end_date(self) -> date:
        if self.end is None:
            return self.start_date
        # An event ending exactly at midnight belongs to the previous day.
        if self.end.time() == datetime.min.time() and self.end > self.start:
            return (self.end - timedelta(seconds=1)).date()
        return self.end.date()

    @property
    def duration_days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    def occurs_on(self, day: date) -> bool:
        return self.start_date <= day <= self.end_date

    @property
    def uid(self) -> str:
        """Stable identifier used for de-duplication."""
        key = f"{norm(self.title)}|{self.start:%Y-%m-%dT%H:%M}|{norm(self.place)}"
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def to_json(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat() if self.end else None
        d["uid"] = self.uid
        return d


def to_local(dt: datetime | date) -> datetime:
    if not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day, tzinfo=TZ)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


_ws = re.compile(r"\s+")
_nonword = re.compile(r"[^\w]+", re.UNICODE)


def norm(s: str) -> str:
    return _nonword.sub(" ", (s or "").casefold()).strip()


def clean_ws(s: str) -> str:
    return _ws.sub(" ", s or "").strip()
