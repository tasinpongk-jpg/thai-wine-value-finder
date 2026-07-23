"""Cellar helpers — a rough drink-window heuristic from vintage + type + body.

Not gospel: these are sensible default windows so you can see at a glance whether a
bottle is one to hold, drink, or has likely peaked. Adjust to taste.
"""
from __future__ import annotations

from typing import Optional


def drink_window(vintage, wine_type, body=None, now_year=None) -> dict:
    """Return {start, end, status, label} for a bottle.

    status ∈ {"Hold", "Ready", "Past peak", "Ready now"}.
    """
    if not vintage:
        return {"start": None, "end": None, "status": "Ready now", "label": "Anytime"}

    v = int(vintage)
    t = (wine_type or "").lower()
    full = bool(body) and "full" in str(body).lower()

    if "sparkling" in t or "champagne" in t:
        start, end = v, v + 8
    elif "dessert" in t or "fortified" in t:
        start, end = v, v + 25
    elif any(k in t for k in ("white", "rosé", "rose", "orange")):
        start, end = v + 1, v + (6 if full else 4)
    else:  # red / other
        start, end = v + 2, v + (12 if full else 7)

    yr = now_year if now_year is not None else _this_year()
    if yr < start:
        status = "Hold"
    elif yr <= end:
        status = "Ready"
    else:
        status = "Past peak"
    return {"start": start, "end": end, "status": status, "label": f"{start}–{end}"}


def _this_year() -> int:
    from datetime import date
    return date.today().year


def current_price_lookup(wines_df) -> dict:
    """{(source, str(source_id)) -> current price_thb} for valuing a cellar."""
    out = {}
    for _, r in wines_df.iterrows():
        out[(r["source"], str(r["source_id"]))] = r.get("price_thb")
    return out
