"""Keyword include filter driven by config/keywords.yaml.

Each category has a list of words. An event is kept if at least one word of
any category occurs in the chosen fields (title, tags, summary, place).
Matching is case-insensitive and by substring, so "konsert" matches
"Joulukonsertti" and "konsertit". Words starting with "re:" are regular
expressions. Exclude words drop an event even if it matched a category.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import Event

log = logging.getLogger(__name__)

FIELDS = ("title", "tags", "summary", "place")
DEFAULT_FIELDS = ("title", "tags")


def _compile(words: list[str]) -> list[re.Pattern]:
    out = []
    for w in words or []:
        w = str(w).strip()
        if not w:
            continue
        if w.startswith("re:"):
            out.append(re.compile(w[3:], re.I))
        else:
            out.append(re.compile(re.escape(w.casefold())))
    return out


def _text(ev: Event, fields) -> str:
    parts = []
    for f in fields:
        v = getattr(ev, f, "")
        parts.append(" ".join(v) if isinstance(v, list) else (v or ""))
    return " | ".join(parts).casefold()


@dataclass
class Category:
    key: str
    label: str
    fields: tuple[str, ...]
    patterns: list[re.Pattern]

    def matches(self, ev: Event) -> bool:
        t = _text(ev, self.fields)
        return any(p.search(t) for p in self.patterns)


class KeywordFilter:
    def __init__(self, data: dict):
        self.enabled = bool(data.get("enabled", True))
        self.categories: list[Category] = []
        for key, c in (data.get("categories") or {}).items():
            c = c or {}
            fields = tuple(c.get("match_in") or DEFAULT_FIELDS)
            bad = set(fields) - set(FIELDS)
            if bad:
                raise ValueError(f"keywords: category {key}: unknown match_in {sorted(bad)}")
            self.categories.append(Category(key, c.get("label", key), fields,
                                            _compile(c.get("words"))))
        ex = data.get("exclude") or {}
        self.exclude_fields = tuple(ex.get("match_in") or DEFAULT_FIELDS)
        self.exclude = _compile(ex.get("words"))

    @classmethod
    def load(cls, path: Path) -> "KeywordFilter | None":
        if not path.exists():
            return None
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    @property
    def labels(self) -> dict[str, str]:
        return {c.key: c.label for c in self.categories}

    def classify(self, ev: Event) -> list[str]:
        return [c.key for c in self.categories if c.matches(ev)]

    def excluded(self, ev: Event) -> bool:
        t = _text(ev, self.exclude_fields)
        return any(p.search(t) for p in self.exclude)

    def apply(self, events: list[Event], bypass_types=("manual",)) -> list[Event]:
        """Tag events with categories; drop non-matching ones (unless filter disabled
        or the event comes from a bypass source type such as manual)."""
        out = []
        dropped = 0
        for ev in events:
            ev.categories = self.classify(ev)
            if ev.source_type in bypass_types or not self.enabled:
                out.append(ev)
            elif ev.categories and not self.excluded(ev):
                out.append(ev)
            else:
                dropped += 1
        log.info("Keyword filter kept %d, dropped %d events", len(out), dropped)
        return out
