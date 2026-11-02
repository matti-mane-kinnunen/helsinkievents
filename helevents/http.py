"""Tiny HTTP helper (stdlib only) with retries and a polite User-Agent."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = (
    "helsinkievents/1.0 (+https://github.com/matti-mane-kinnunen/helsinkievents)"
)


def get(url: str, *, timeout: int = 30, retries: int = 3, accept: str = "*/*") -> bytes:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": accept}
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if 400 <= e.code < 500 and e.code != 429:
                break  # no point retrying client errors
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, retries, last)
        time.sleep(2 * attempt)
    raise RuntimeError(f"GET {url} failed: {last}")


def get_json(url: str, **kw) -> dict:
    return json.loads(get(url, accept="application/json", **kw))


def get_text(url: str, **kw) -> str:
    return get(url, **kw).decode("utf-8", errors="replace")
