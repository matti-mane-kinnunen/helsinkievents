"""Convert a GitHub issue created with .github/ISSUE_TEMPLATE/add-event.yml
into a YAML file in events/manual/.

Usage:
    python -m helevents.issue_to_event --body-file body.md --issue 12 [--outdir events/manual]
Prints the written path. Exits 1 with a Finnish error message on invalid input.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

from .sources.manual import ManualEventError, to_event

# Issue-form labels (see add-event.yml) -> YAML fields
LABELS = {
    "tapahtuman nimi": "title",
    "päivämäärä": "date",
    "alkamisaika": "time",
    "päättymispäivä": "end_date",
    "päättymisaika": "end_time",
    "paikka": "place",
    "osoite": "address",
    "linkki": "url",
    "kuvaus": "summary",
}
EMPTY = {"", "_no response_", "none", "-"}


def parse_issue_form(body: str) -> dict:
    fields: dict[str, str] = {}
    parts = re.split(r"^###\s+(.+?)\s*$", body.replace("\r\n", "\n"), flags=re.M)
    # parts = [preamble, label1, value1, label2, value2, ...]
    for label, value in zip(parts[1::2], parts[2::2]):
        key = LABELS.get(label.strip().rstrip("*").strip().casefold())
        v = value.strip()
        if key and v.casefold() not in EMPTY:
            fields[key] = v
    return fields


def norm_time(t: str) -> str:
    t = t.strip().replace(".", ":")
    if re.fullmatch(r"\d{1,2}", t):
        t += ":00"
    if not re.fullmatch(r"\d{1,2}:\d{2}", t):
        raise ManualEventError(f"Kellonaika '{t}' ei kelpaa – käytä muotoa 18:30")
    h, m = t.split(":")
    return f"{int(h):02d}:{m}"


def norm_date(d: str) -> str:
    d = d.strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", d)
    if m:
        return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        raise ManualEventError(f"Päivämäärä '{d}' ei kelpaa – käytä muotoa 2026-11-14 tai 14.11.2026")
    return d


def to_yaml_dict(f: dict) -> dict:
    if not f.get("title") or not f.get("date"):
        raise ManualEventError("Tapahtuman nimi ja päivämäärä ovat pakollisia")
    d = norm_date(f["date"])
    out: dict = {"title": f["title"]}
    out["start"] = f"{d} {norm_time(f['time'])}" if f.get("time") else d
    if f.get("end_date") or f.get("end_time"):
        ed = norm_date(f["end_date"]) if f.get("end_date") else d
        out["end"] = f"{ed} {norm_time(f['end_time'])}" if f.get("end_time") else ed
    for k in ("place", "address", "url", "summary"):
        if f.get(k):
            out[k] = f[k]
    if out.get("url") and not re.match(r"https?://", out["url"]):
        raise ManualEventError("Linkin pitää alkaa http:// tai https://")
    to_event(out, origin="issue")  # validate with the same rules as the build
    return out


def slugify(s: str, maxlen: int = 40) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].rstrip("-") or "tapahtuma"


def write_event(fields: dict, outdir: Path, issue: str | None = None) -> Path:
    data = to_yaml_dict(fields)
    name = f"{data['start'][:10]}-{slugify(data['title'])}"
    if issue:
        name += f"-i{issue}"
    path = outdir / f"{name}.yaml"
    outdir.mkdir(parents=True, exist_ok=True)
    header = f"# Lisätty GitHub-issuesta #{issue}\n" if issue else ""
    path.write_text(header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--issue")
    ap.add_argument("--outdir", default="events/manual")
    a = ap.parse_args(argv)
    body = Path(a.body_file).read_text(encoding="utf-8")
    try:
        path = write_event(parse_issue_form(body), Path(a.outdir), a.issue)
    except ManualEventError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
