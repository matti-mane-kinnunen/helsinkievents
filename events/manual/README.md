# Käsin lisätyt tapahtumat

Each `.yaml` file here is one event (or a list of events). Files are picked up
by the nightly build. Past events are simply not shown; they can be deleted
whenever convenient.

```yaml
title: Jazz-ilta Savoyssa         # required
start: 2026-11-14 19:00           # required; "2026-11-14" = all-day
end: 2026-11-14 22:00             # optional
place: Savoy-teatteri             # optional but recommended
address: Kasarmikatu 46-48        # optional
url: https://example.org          # optional
summary: Lyhyt kuvaus (max ~400 merkkiä).  # optional
status: cancelled                 # optional: scheduled | cancelled | postponed
```

Check files with `python -m helevents.validate`.
