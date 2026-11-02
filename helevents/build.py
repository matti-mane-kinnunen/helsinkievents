"""Build pipeline: config -> sources -> filter/dedupe -> site/.

Usage:
    python -m helevents.build [--config config/sources.yaml] [--out site] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from .model import TZ, Event
from .render import render_page
from .sources import REGISTRY

log = logging.getLogger("helevents")
ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Result:
    today: date
    window_end: date
    today_events: list[Event]
    upcoming: dict[date, list[Event]]
    ongoing: list[Event]
    source_stats: list[dict] = field(default_factory=list)
    generated: datetime = field(default_factory=lambda: datetime.now(TZ))

    @property
    def all_events(self) -> list[Event]:
        seen, out = set(), []
        for ev in self.today_events + [e for d in self.upcoming.values() for e in d] + self.ongoing:
            if ev.uid not in seen:
                seen.add(ev.uid)
                out.append(ev)
        return out


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg.setdefault("window_days", 31)
    cfg.setdefault("sources", [])
    cfg.setdefault("filters", {})
    return cfg


def collect(cfg: dict, today: date, root: Path = ROOT) -> tuple[list[Event], list[dict]]:
    window_end = today + timedelta(days=int(cfg["window_days"]))
    events: list[Event] = []
    stats: list[dict] = []
    for scfg in cfg["sources"]:
        if not scfg.get("enabled", True):
            continue
        kind = scfg.get("type")
        fetch = REGISTRY.get(kind)
        name = scfg.get("name", kind)
        if not fetch:
            log.error("Unknown source type %r (%s) – skipped", kind, name)
            stats.append({"name": name, "type": kind, "ok": False, "count": 0,
                          "error": "unknown type"})
            continue
        try:
            got = fetch({**scfg, "_root": str(root)}, today, window_end)
            log.info("%-40s %5d events", name, len(got))
            stats.append({"name": name, "type": kind, "ok": True, "count": len(got)})
            if not got and kind != "manual":
                log.warning("%s returned 0 events – check the source/filters", name)
            events += got
        except Exception as e:  # a failing source must not break the whole build
            log.exception("Source %s failed", name)
            stats.append({"name": name, "type": kind, "ok": False, "count": 0,
                          "error": str(e)[:200]})
    return events, stats


def apply_filters(events: list[Event], filters: dict) -> list[Event]:
    pats = [re.compile(p, re.I) for p in filters.get("exclude_title", [])]
    places = [re.compile(p, re.I) for p in filters.get("exclude_place", [])]
    hide_cancelled = filters.get("hide_cancelled", False)
    out = []
    for ev in events:
        if any(p.search(ev.title) for p in pats):
            continue
        if any(p.search(ev.place) for p in places):
            continue
        if hide_cancelled and ev.status == "cancelled":
            continue
        out.append(ev)
    return out


def dedupe(events: list[Event]) -> list[Event]:
    """Keep the first occurrence (sources earlier in config win)."""
    seen: dict[str, Event] = {}
    for ev in events:
        if ev.uid not in seen:
            seen[ev.uid] = ev
        else:
            kept = seen[ev.uid]
            # fill gaps from the duplicate
            for attr in ("summary", "url", "address", "place"):
                if not getattr(kept, attr) and getattr(ev, attr):
                    setattr(kept, attr, getattr(ev, attr))
    return list(seen.values())


def organise(events: list[Event], today: date, window_days: int,
             max_event_days: int = 7) -> Result:
    window_end = today + timedelta(days=window_days)
    events = sorted(events, key=lambda e: (e.start, e.title.casefold()))
    today_events: list[Event] = []
    upcoming: dict[date, list[Event]] = {}
    ongoing: list[Event] = []
    for ev in events:
        if ev.end_date < today or ev.start_date > window_end:
            continue
        if ev.duration_days > max_event_days:
            ongoing.append(ev)
        elif ev.occurs_on(today):
            today_events.append(ev)
        elif ev.start_date > today:
            upcoming.setdefault(ev.start_date, []).append(ev)
    ongoing.sort(key=lambda e: (e.end_date, e.title.casefold()))
    return Result(today, window_end, today_events, dict(sorted(upcoming.items())), ongoing)


def build(cfg: dict, today: date, out: Path, root: Path = ROOT) -> Result:
    raw, stats = collect(cfg, today, root)
    events = dedupe(apply_filters(raw, cfg["filters"]))
    res = organise(events, today, int(cfg["window_days"]),
                   int(cfg["filters"].get("max_event_days", 7)))
    res.source_stats = stats
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_page(res, cfg), encoding="utf-8")
    (out / "events.json").write_text(json.dumps({
        "generated": res.generated.isoformat(),
        "today": today.isoformat(),
        "sources": stats,
        "events": [e.to_json() for e in res.all_events],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    log.info("Wrote %s: %d today, %d upcoming, %d ongoing (from %d raw)",
             out, len(res.today_events), sum(map(len, res.upcoming.values())),
             len(res.ongoing), len(raw))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(ROOT / "config" / "sources.yaml"))
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    today = date.fromisoformat(a.today) if a.today else datetime.now(TZ).date()
    cfg_path = Path(a.config)
    res = build(load_config(cfg_path), today, Path(a.out), cfg_path.resolve().parent.parent)
    if not res.all_events:
        failed = [s["name"] for s in res.source_stats if not s["ok"]]
        log.error("No events at all (failed sources: %s) – refusing to publish an empty page",
                  ", ".join(failed) or "none")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
