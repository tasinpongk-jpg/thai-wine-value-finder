"""wineplus.co.th — WooCommerce Store API. Type & country are categories."""
from __future__ import annotations

from sources import SOURCES, WINE_TYPE_CATEGORY_HINTS
from scrapers.base import PoliteSession
from scrapers import woocommerce as wc
from enrich import normalize as N

KEY = "wineplus"
CFG = SOURCES[KEY]

NON_WINE = {"spirits, craft beer & others", "spirits", "craft beer",
            "beer", "others", "gift", "accessories", "sake"}


def _is_wine(obj) -> bool:
    cats = [c.strip().lower() for c in wc.categories(obj)]
    return not any(c in NON_WINE for c in cats)


def parse(obj):
    cats = wc.categories(obj)
    w = wc.common_wine(obj, KEY)
    w.wine_type = N.canonical_wine_type(cats)
    for c in cats:
        cl = c.strip().lower()
        if cl in WINE_TYPE_CATEGORY_HINTS or cl in NON_WINE:
            continue
        w.country = c
        break
    amap = wc.attr_map(obj)
    size = wc.first_attr(amap, "Bottle size", "pa_bottle-size", "bottle size")
    w.size_ml = N.parse_size_ml(size or w.name)
    w.vintage = N.parse_vintage(w.name)
    return w


def scrape(session=None):
    session = session or PoliteSession()
    objs = wc.fetch_all(session, CFG["base"], CFG["products_path"], CFG["params"])
    return [parse(o) for o in objs if _is_wine(o)]
