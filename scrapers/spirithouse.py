"""spirithouse.com — WooCommerce Store API. Rich pa_* attributes incl. Vivino rating."""
from __future__ import annotations

import re

from sources import SOURCES
from scrapers.base import PoliteSession, strip_html
from scrapers import woocommerce as wc
from enrich import normalize as N
from enrich.tasting import parse_sections

KEY = "spirithouse"
CFG = SOURCES[KEY]


def _float(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def parse(obj):
    w = wc.common_wine(obj, KEY)
    amap = wc.attr_map(obj)

    wtype = wc.first_attr(amap, "pa_wine-type", "wine type", "wine-type", "type")
    w.wine_type = N.canonical_wine_type([wtype] if wtype else [], text=w.name)

    vintage = wc.first_attr(amap, "pa_vintage", "vintage")
    w.vintage = N.parse_vintage(vintage) or N.parse_vintage(w.name)

    vol = wc.first_attr(amap, "pa_volume", "volume")
    w.size_ml = N.parse_size_ml(vol or w.name)

    w.country = wc.first_attr(amap, "pa_country", "country")
    w.region = wc.first_attr(amap, "pa_region", "region")
    grapes = wc.all_attr(amap, "pa_varietals", "varietals", "pa_grape", "grape")
    w.grape = ", ".join(grapes) if grapes else None

    viv = _float(wc.first_attr(amap, "pa_vivino-rating", "vivino rating", "vivino-rating"))
    if viv:
        w.vivino_rating = viv
        w.vivino_source = "site"

    # body / alcohol / tasting prose
    style = wc.first_attr(amap, "pa_style", "style")
    w.body = style.split(",")[0].strip() if style else None
    w.alcohol = wc.first_attr(amap, "pa_alcohol", "alcohol")

    desc_full = strip_html(obj.get("description"))
    sec = parse_sections(desc_full)
    sec_short = parse_sections(strip_html(obj.get("short_description")))
    w.appearance = N.short_desc(sec.get("appearance"), 200)
    w.nose = N.short_desc(sec.get("nose"), 240)
    w.palate = N.short_desc(sec.get("palate"), 240)

    pairing = sec_short.get("pairing") or ", ".join(
        wc.all_attr(amap, "pa_food-pairing", "food pairing")[:4])
    if pairing:
        pairing = re.split(r"READINESS|Aged for", pairing, flags=re.I)[0]
        w.pairing = N.short_desc(pairing, 180)

    # nicer blurb: the lead-in before the "Tasting Notes" dump
    lead = re.split(r"Tasting Notes", desc_full, flags=re.I)[0] if desc_full else ""
    lead = re.sub(r"^Key characteristics\s*:\s*", "", lead, flags=re.I).strip()
    w.description = N.short_desc(lead or desc_full)
    return w


def scrape(session=None):
    session = session or PoliteSession()
    objs = wc.fetch_all(session, CFG["base"], CFG["products_path"], CFG["params"])
    return [parse(o) for o in objs]
