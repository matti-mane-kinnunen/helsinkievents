"""Validate config and manual events. Used by CI and handy before committing.

    python -m helevents.validate
"""
from __future__ import annotations

import sys
from pathlib import Path

from .build import ROOT, load_config
from .sources import REGISTRY
from .sources.manual import load_dir


def main() -> int:
    errors: list[str] = []
    cfg = load_config(ROOT / "config" / "sources.yaml")
    for s in cfg["sources"]:
        if s.get("type") not in REGISTRY:
            errors.append(f"config: unknown source type {s.get('type')!r}")
        if s.get("type") == "ical" and not s.get("url"):
            errors.append(f"config: ical source {s.get('name')!r} needs url")
        if s.get("type") == "jsonld" and not (s.get("url") or s.get("urls")):
            errors.append(f"config: jsonld source {s.get('name')!r} needs url(s)")
    events, errs = load_dir(ROOT / "events" / "manual")
    errors += errs
    for e in errors:
        print("ERROR", e)
    print(f"{len(events)} manual events OK, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
