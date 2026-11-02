# Backlog

Status: 🔴 important · 🟡 normal · ⚪ idea. Move items to "Done" with a date.

## Verify / data issues
- 🔴 **B-1 Verify Linked Events against the live API.** Not reachable from the dev
  sandbox; built from the documented schema + fixtures. On the first Actions run check
  the log ("API reports N events"), and that times, places and links look right.
  Specifically confirm `division=helsinki` and `super_event_type=none` are accepted.
- 🔴 **B-2 Verify the YSO keyword ids** in `config/sources.yaml` (musiikki p1808,
  konsertit p11185, teatteritaide p2625, tanssi p1278, elokuvat p1235, näyttelyt p5121,
  kulttuuritapahtumat p360) via `https://api.hel.fi/linkedevents/v1/keyword/?text=…`.
- 🟡 **B-3 Tune the scope** after seeing real volumes: events/day, unwanted categories,
  title exclude regexes. Consider `max_pages` if the result is cut off (warning in log).
- 🟡 **B-4 Fuzzy de-duplication.** Same event with slightly different titles or start
  times across sources is not merged (exact normalised match only).
- ⚪ B-5 Linked Events sometimes has events with only Swedish/English text; check
  how common and whether to mark the language.

## Fixes / technical
- 🟡 B-6 When the page is opened on a later day than it was built (stale page),
  multi-day events that started on an earlier day are not moved into "Tänään".
- 🟡 B-7 Alert on failure: GitHub emails the repo owner on failed scheduled runs by
  default — confirm notifications are on. Optionally open an issue automatically.
- ⚪ B-8 Keep-alive: GitHub disables schedules after 60 days without repo activity.
  Could add a monthly keep-alive commit or rely on manual re-enable.
- ⚪ B-9 Housekeeping workflow that deletes past manual events (e.g. older than 30 days).
- ⚪ B-10 Pin GitHub Actions to commit SHAs.
- 🟡 B-18 First run (2026-11-02) warned "Node.js 20 is deprecated": bump actions
  (checkout, setup-python, configure-pages, upload-pages-artifact, deploy-pages) to
  their latest Node 24 majors. Also note: `ubuntu-latest` moves to Ubuntu 26.

## Ideas / features
- 🟡 B-11 More sources: venue iCal feeds, JSON-LD pages (e.g. clubs, theatres),
  Tiketti/Lippupiste (check terms of use), university/HSY calendars.
- ⚪ B-21 Day headers show the total count even when a filter button / search hides
  some events; update counts client-side.
- ⚪ B-13 Optional Claude API summaries (D-5 alternative) for sources with poor text.
- ⚪ B-14 Publish `events.ics` so the list can be subscribed to in a calendar app.
- ⚪ B-15 Free/price info (Linked Events `offers`).
- ⚪ B-16 "Weekend" section; map links for places.
- ⚪ B-17 A Claude skill for "add event from a link" (fetch page → YAML → PR).

## Done
- 2026-11-02 B-12 Category filter buttons (from keywords.yaml) and badges on cards.
- 2026-11-02 Keyword include filter `config/keywords.yaml` (music, performances, openings).
- 2026-11-02 Fixed: search box did not hide cards (CSS `display:grid` overrode `hidden`).
- 2026-11-02 Initial version: sources (manual, Linked Events, iCal, JSON-LD), page,
  nightly build, issue form, docs, tests.
