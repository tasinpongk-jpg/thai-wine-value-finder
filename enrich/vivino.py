"""Best-effort Vivino community-rating lookup.

Vivino actively blocks scrapers, so this is intentionally tolerant: every result
(including misses) is cached, lookups are capped, and any failure simply leaves the
wine unrated. Spirit House already supplies Vivino ratings natively, so this only
fills gaps for the other sites.
"""
from __future__ import annotations

import json
import os

from enrich.normalize import normalize_name

VIVINO_CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "vivino_cache.json")
EXPLORE_URL = "https://www.vivino.com/api/explore/explore"


def cache_key(name, vintage) -> str:
    return f"{normalize_name(name)}|{vintage or ''}"


def _load_cache(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_cache(cache, path):
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False)


def parse_vivino_response(data):
    """Find the first plausible rating anywhere in Vivino's (variable) JSON."""
    found = {}

    def walk(o):
        if "rating" in found:
            return
        if isinstance(o, dict):
            if "ratings_average" in o:
                try:
                    ra = float(o.get("ratings_average"))
                    if ra > 0:
                        found["rating"] = ra
                        rc = o.get("ratings_count")
                        found["count"] = int(rc) if rc is not None else None
                        return
                except (TypeError, ValueError):
                    pass
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return {"rating": found["rating"], "count": found.get("count")} if found else None


def lookup(name, vintage, session):
    """Single best-effort network lookup. Returns {rating,count} or None."""
    q = f"{name} {vintage}" if vintage else name
    try:
        r = session.s.get(EXPLORE_URL, params={"q": q, "per_page": 1},
                          headers={"Accept": "application/json"}, timeout=session.timeout)
        if r.status_code != 200:
            return None
        return parse_vivino_response(r.json())
    except Exception:
        return None


def enrich_wines(wines, session=None, limit=120, cache_path=VIVINO_CACHE,
                 give_up_after=12, log=print):
    """Fill vivino_rating for wines that lack one. Returns the number of hits.

    Stops early after ``give_up_after`` fresh lookups with zero hits — Vivino is
    almost certainly blocking, so there's no point hammering it.
    """
    cache = _load_cache(cache_path)
    hits, net = 0, 0
    for w in wines:
        if w.vivino_rating is not None or not w.name:
            continue
        key = cache_key(w.name, w.vintage)
        if key in cache:
            res = cache[key]
        elif net < limit:
            if hits == 0 and net >= give_up_after:
                break  # clearly blocked
            net += 1
            if session is None:
                from scrapers.base import PoliteSession
                session = PoliteSession()
            res = lookup(w.name, w.vintage, session)
            cache[key] = res
        else:
            continue
        if res:
            w.vivino_rating = res.get("rating")
            w.vivino_count = res.get("count")
            w.vivino_source = "lookup"
            hits += 1
    _save_cache(cache, cache_path)
    log(f"Vivino: {hits} hits from {net} lookups ({len(cache)} cached)")
    return hits
