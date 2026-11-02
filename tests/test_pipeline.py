import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from helevents import build, http
from helevents.issue_to_event import parse_issue_form, write_event
from helevents.model import Event
from helevents.render import time_label
from helevents.sources import ical, jsonld, linkedevents, manual
from helevents.sources.manual import ManualEventError
from helevents.text import summarize

FX = Path(__file__).parent / "fixtures"
TZ = ZoneInfo("Europe/Helsinki")
TODAY = date(2026, 11, 2)


def ev(title, start, end=None, **kw):
    return Event(title=title, start=start, end=end, source=kw.pop("source", "t"), **kw)


# ---------------------------------------------------------------- text
def test_summarize_prefers_sentence_boundary():
    first = "Ensimmäinen lause on tässä ja se on riittävän pitkä katkaisuun."
    assert summarize(first + " " + "sana " * 80, 100) == first


def test_summarize_strips_html_and_adds_ellipsis():
    out = summarize("<p>" + "abc " * 100 + "</p>", 50)
    assert out.endswith("…") and "<" not in out and len(out) <= 51


# ---------------------------------------------------------------- linked events
@pytest.fixture
def fake_api(monkeypatch):
    pages = [json.loads((FX / f"linkedevents_page{i}.json").read_text()) for i in (1, 2)]
    calls = []

    def get_json(url, **kw):
        calls.append(url)
        return pages[len(calls) - 1]

    monkeypatch.setattr(http, "get_json", get_json)
    return calls


def test_linkedevents_parsing(fake_api):
    cfg = {"name": "LE", "params": {"division": "helsinki", "keyword": ["yso:p1808", "yso:p5121"]},
           "delay": 0}
    evs = linkedevents.fetch(cfg, TODAY, date(2026, 12, 3))
    assert len(fake_api) == 2
    assert "keyword=yso:p1808,yso:p5121" in fake_api[0]
    assert "super_event_type=none" in fake_api[0]
    titles = [e.title for e in evs]
    assert "Toistuva emo" not in titles               # recurring parent dropped
    jazz = evs[0]
    assert jazz.start == datetime(2026, 11, 2, 18, 0, tzinfo=TZ)   # UTC -> Helsinki
    assert jazz.place == "Stoa" and jazz.address == "Turunlinnantie 1, Helsinki"
    assert jazz.summary == "Illan tähtenä trio. Toinen lause on tässä."
    assert jazz.url == "https://www.stoa.fi/jazz"
    eng = next(e for e in evs if e.title == "Only English title")
    assert eng.status == "cancelled"
    assert eng.summary == "Kuvaus vain pitkänä tekstinä."
    assert eng.url.startswith("https://tapahtumat.hel.fi/")


def test_linkedevents_exclude_keywords(fake_api):
    evs = linkedevents.fetch({"exclude_keywords": ["yso:p4354"], "delay": 0}, TODAY, TODAY)
    assert "Satutunti kirjastossa" not in [e.title for e in evs]


# ---------------------------------------------------------------- ical / jsonld
def test_ical_parsing_and_recurrence():
    evs = ical.parse((FX / "sample.ics").read_bytes(), "ICS", TODAY, date(2026, 12, 3))
    by = {}
    for e in evs:
        by.setdefault(e.title, []).append(e)
    runo = by["Runoilta"][0]
    assert runo.place == "Kirjakauppa Arkadia" and runo.address == "Nervanderinkatu 11"
    assert runo.start.hour == 19
    market = by["Viikonloppumarkkinat"][0]
    assert market.all_day and market.duration_days == 2
    # weekly from 2.10, 10 times -> 2.11 .. 4.12 overlaps window: 2.11, 9.11, 16.11, 23.11, 30.11
    assert len(by["Viikkojamit"]) == 5


def test_jsonld_parsing():
    evs = jsonld.parse((FX / "jsonld.html").read_text(), "Web", "https://example.org/x")
    assert [e.title for e in evs] == ["Bändi-ilta", "Päiväapu"]
    b = evs[0]
    assert b.place == "Tavastia" and "Urho Kekkosen" in b.address
    assert b.duration_days == 2  # ends after midnight
    assert evs[1].all_day and evs[1].place == "Kallio" and evs[1].url == "https://example.org/x"


# ---------------------------------------------------------------- manual + issues
def test_manual_formats(tmp_path):
    (tmp_path / "a.yaml").write_text(
        "title: A\nstart: 2026-11-10 18:30\nend: 2026-11-10 20:00\nplace: X\n")
    (tmp_path / "b.yaml").write_text("- title: B\n  start: 2026-11-11\n- title: C\n  start: 12.11.2026 9.15\n")
    (tmp_path / "bad.yaml").write_text("title: Bad\nstart: huomenna\n")
    (tmp_path / "unknown.yaml").write_text("title: U\nstart: 2026-11-11\ncolour: red\n")
    evs, errs = manual.load_dir(tmp_path)
    assert sorted(e.title for e in evs) == ["A", "B", "C"]
    assert len(errs) == 2
    b = next(e for e in evs if e.title == "B")
    assert b.all_day
    c = next(e for e in evs if e.title == "C")
    assert (c.start.hour, c.start.minute) == (9, 15)


def test_manual_end_before_start():
    with pytest.raises(ManualEventError):
        manual.to_event({"title": "x", "start": "2026-11-10 18:00", "end": "2026-11-10 17:00"})


def test_issue_to_event(tmp_path):
    f = parse_issue_form((FX / "issue_body.md").read_text())
    assert "end_date" not in f
    path = write_event(f, tmp_path, "12")
    assert path.name == "2026-11-14-jazz-ilta-savoyssa-i12.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["start"] == "2026-11-14 19:00" and data["end"] == "2026-11-14 22:00"
    assert data["summary"].startswith('Ilta täynnä jazzia: "lainausmerkit"')
    e = manual.load_file(path)[0]
    assert e.place == "Savoy-teatteri" and e.end.hour == 22


def test_issue_invalid():
    with pytest.raises(ManualEventError):
        write_event({"title": "x", "date": "ensi viikolla"}, Path("/tmp"), "1")
    with pytest.raises(ManualEventError):
        write_event({"title": "x", "date": "2026-11-14", "url": "javascript:alert(1)"}, Path("/tmp"))


# ---------------------------------------------------------------- organise / render
def test_organise_sections():
    d = lambda day, h=18: datetime(2026, 11, day, h, tzinfo=TZ)
    events = [
        ev("Tänään", d(2)),
        ev("Huomenna", d(3)),
        ev("Eilen", d(1)),
        ev("Alkoi eilen jatkuu", d(1), d(2, 20)),
        ev("Pitkä näyttely", datetime(2026, 9, 1, tzinfo=TZ), datetime(2027, 1, 1, tzinfo=TZ)),
        ev("Liian kaukana", datetime(2026, 12, 20, 18, tzinfo=TZ)),
    ]
    r = build.organise(events, TODAY, 31, 7)
    assert [e.title for e in r.today_events] == ["Alkoi eilen jatkuu", "Tänään"]
    assert list(r.upcoming) == [date(2026, 11, 3)]
    assert [e.title for e in r.ongoing] == ["Pitkä näyttely"]


def test_dedupe_and_filters():
    t = datetime(2026, 11, 5, 19, tzinfo=TZ)
    a = ev("Jazz Ilta!", t, place="Savoy", source="manual")
    b = ev("jazz ilta", t, place="savoy", summary="desc", source="api")
    out = build.dedupe([a, b])
    assert len(out) == 1 and out[0].source == "manual" and out[0].summary == "desc"
    f = build.apply_filters([ev("Satutunti", t), ev("Konsertti", t)],
                            {"exclude_title": ["satutunti"]})
    assert [e.title for e in f] == ["Konsertti"]


def test_time_labels():
    t = datetime(2026, 11, 5, 19, 0, tzinfo=TZ)
    assert time_label(ev("x", t, t.replace(hour=21, minute=30))) == "klo 19.00–21.30"
    assert time_label(ev("x", t)) == "klo 19.00"
    assert time_label(ev("x", datetime(2026, 11, 5, tzinfo=TZ), all_day=True)) == "koko päivä"
    assert time_label(ev("x", t, datetime(2026, 11, 7, 2, tzinfo=TZ))) == "5.11.–7.11."


def test_full_build(tmp_path, fake_api, monkeypatch):
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    root = tmp_path
    (root / "events" / "manual").mkdir(parents=True)
    (root / "events" / "manual" / "x.yaml").write_text(
        "title: <script>alert(1)</script>\nstart: 2026-11-02 12:00\nplace: Tori\n")
    (root / "cal.ics").write_bytes((FX / "sample.ics").read_bytes())
    cfg = {
        "window_days": 31,
        "site": {"title": "Testi", "repo_url": "https://github.com/x/y"},
        "filters": {"exclude_title": ["satutunti"]},
        "sources": [
            {"type": "manual", "path": "events/manual"},
            {"type": "linkedevents", "name": "LE", "delay": 0},
            {"type": "ical", "name": "ICS", "url": (root / "cal.ics").as_uri()},
            {"type": "jsonld", "name": "Broken", "urls": ["http://nonexistent.invalid/"]},
            {"type": "nope", "name": "Unknown"},
        ],
    }
    res = build.build(cfg, TODAY, root / "site", root)
    html = (root / "site" / "index.html").read_text()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "<script>alert(1)" not in html
    assert "Jazz-konsertti" in html and "Runoilta" in html and "Satutunti" not in html
    assert "Peruttu" in html
    assert 'id="tanaan"' in html and "maanantai 2. marraskuuta" in html
    data = json.loads((root / "site" / "events.json").read_text())
    names = {s["name"]: s for s in data["sources"]}
    assert names["Unknown"]["ok"] is False
    assert names["Broken"]["ok"] is True and names["Broken"]["count"] == 0  # per-URL failure tolerated
    assert len(res.today_events) == 3  # manual + jazz + weekly jam on 2.11
