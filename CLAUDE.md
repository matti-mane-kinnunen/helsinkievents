# Instructions for Claude

## Adding an event
When asked to add an event:

1. Create `events/manual/YYYY-MM-DD-<ascii-slug>.yaml` (slug: lowercase title,
   ä→a, ö→o, non-alphanumerics → `-`, max ~40 chars). Format:

   ```yaml
   title: Jazz-ilta Savoyssa
   start: 2026-11-14 19:00      # local Helsinki time; date only = all-day
   end: 2026-11-14 22:00        # optional
   place: Savoy-teatteri
   address: Kasarmikatu 46-48   # optional
   url: https://…               # optional, http(s) only
   summary: 1–3 sentences in Finnish.   # optional
   ```
   Allowed keys: title, start, end, place, address, url, summary, status, tags.
2. If the user gives a link, fetch it and take the facts from there; do not
   invent times, prices or descriptions. Ask if the date or place is unclear.
3. Run `python -m helevents.validate` (and `python -m pytest -q` if code changed).
4. Commit with message `Lisää tapahtuma: <title>` and push to `main`
   (the push triggers a rebuild). If you cannot push, tell the user the exact
   file to commit.

## Working on the code
* Keep the page Finnish; keep code/comments/docs in English.
* Record every non-trivial decision in `docs/DECISIONS.md` (next D-number).
* Add ideas, fixes and data issues to `docs/BACKLOG.md`.
* Tests must stay offline (use fixtures in `tests/fixtures/`).
