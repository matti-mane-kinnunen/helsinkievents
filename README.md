# Helsingin tapahtumat

A small static site that gathers Helsinki events from several sources and
publishes them as **one web page on GitHub Pages**, rebuilt **every night at
03:00 Finnish time**.

The page (in Finnish) shows, for every event: date, time, place, title and a
short summary, split into

1. **Tänään** – today's events
2. **Seuraavan kuukauden tapahtumat** – the next 31 days, grouped by day
3. **Pitkäkestoiset** – exhibitions and other events longer than a week (collapsed)

It also has a client-side search box and publishes the data as `events.json`.

Live page (after setup): https://matti-mane-kinnunen.github.io/helsinkievents/

## How it works

```
config/sources.yaml ──► helevents.build ──► site/index.html + site/events.json ──► GitHub Pages
                         │
                         ├─ manual        events/manual/*.yaml  (added by hand, Claude or GitHub issues)
                         ├─ linkedevents  City of Helsinki Linked Events API (api.hel.fi)
                         ├─ ical          any .ics calendar feed
                         └─ jsonld        any web page with schema.org Event JSON-LD
```

* Every source returns normalised `Event` objects (`helevents/model.py`).
* Global filters (title/place regexes) are applied, then duplicates
  (same title + start time + place) are removed — the source listed first in the
  config wins, so manual entries override API data.
* A failing source is logged and shown as "⚠ haku epäonnistui" in the page
  footer; the rest of the page is still built. If **no** events at all are
  found the build fails, so the previous page stays online.
* If the nightly build ever fails, the published page notices it is stale and
  moves the correct day into "Tänään" in the browser, with a notice.

## Repository layout

| Path | What |
|---|---|
| `config/sources.yaml` | Sources, keyword filters, window length, site title |
| `events/manual/` | Hand-added events, one YAML file each |
| `helevents/` | Python package: `build.py` (pipeline), `render.py` (HTML), `sources/*` |
| `helevents/issue_to_event.py` | Turns a GitHub issue form into an event file |
| `helevents/validate.py` | Checks config + manual events |
| `tests/` | pytest suite with offline fixtures |
| `.github/workflows/build.yml` | Nightly 03:00 build + deploy to Pages |
| `.github/workflows/add-event.yml` | Issue → event file → rebuild |
| `.github/ISSUE_TEMPLATE/add-event.yml` | "Lisää tapahtuma" issue form |
| `docs/DECISIONS.md` | Decision log |
| `docs/BACKLOG.md` | Ideas, fixes, data issues |
| `CLAUDE.md` | Instructions for Claude when working in this repo |

## One-time setup on GitHub

1. Push this code to `main`.
2. **Settings → Pages → Build and deployment → Source: _GitHub Actions_.**
3. **Settings → Actions → General → Workflow permissions:** _Read and write
   permissions_ (needed by the issue workflow to commit event files).
4. Create two labels (Issues → Labels): `tapahtuma` and `hyväksytty`.
5. Run the first build: **Actions → Build and deploy page → Run workflow.**

Note: GitHub disables scheduled workflows in repositories with no activity for
60 days. If that happens, re-enable it under Actions (one click).

## Adding events

### 1. With Claude
Ask Claude (in this project, or Claude Code in a clone of the repo) e.g.
*"Lisää tapahtuma: Jazz-ilta Savoyssa 14.11. klo 19–22, Kasarmikatu 46"*.
Claude creates `events/manual/<date>-<slug>.yaml` following `CLAUDE.md`,
runs the validator, and you commit/push (or Claude pushes if it has access).
The push triggers a rebuild automatically.

### 2. With a GitHub issue
Open **Issues → New issue → "Lisää tapahtuma"** and fill the form.

* Issues by the owner / collaborators are converted immediately: the workflow
  commits the YAML file, comments, closes the issue and rebuilds the page.
* Issues by anyone else wait until a maintainer adds the label `hyväksytty`.
* If the form has errors (bad date etc.), the bot comments with the reason.

### 3. By hand
Create a YAML file in `events/manual/` — format in
[`events/manual/README.md`](events/manual/README.md).

## Adding sources

Edit `config/sources.yaml`:

* **Linked Events filters** – change `params.keyword` (YSO keyword ids, OR-ed),
  `division`, or any other [API parameter](https://dev.hel.fi/apis/linkedevents).
  Look up keyword ids at `https://api.hel.fi/linkedevents/v1/keyword/?text=jazz`.
* **iCal feed** – add `type: ical` with `url:`.
* **Web page** – if the page embeds schema.org Event JSON-LD (check "view
  source" for `application/ld+json`), add `type: jsonld` with `urls:`.
* **Something else** – write `helevents/sources/<name>.py` with
  `fetch(cfg, start, end) -> list[Event]` and register it in
  `helevents/sources/__init__.py`.

## Local development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q                 # tests (offline)
python -m helevents.validate        # check config + manual events
python -m helevents.build           # fetch + build into site/
open site/index.html
python -m helevents.build --today 2026-12-01   # pretend it's another day
```

Requires Python 3.10+.
