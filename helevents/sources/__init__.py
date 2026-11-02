"""Source registry. Add a new source type by writing a module with
`fetch(cfg: dict, start: date, end: date) -> list[Event]` and registering it here."""
from . import ical, jsonld, linkedevents, manual

REGISTRY = {
    "linkedevents": linkedevents.fetch,
    "ical": ical.fetch,
    "jsonld": jsonld.fetch,
    "manual": manual.fetch,
}
