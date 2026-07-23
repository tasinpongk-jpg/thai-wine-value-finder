"""winedutyfree.com — WooCommerce Store API. Type/vintage live in the (Thai) name."""
from __future__ import annotations

from sources import SOURCES
from scrapers.base import PoliteSession
from scrapers import woocommerce as wc
from enrich import normalize as N

KEY = "winedutyfree"
CFG = SOURCES[KEY]

_THAI_COUNTRY = {
    "อิตาลี": "Italy", "ฝรั่งเศส": "France", "สเปน": "Spain", "ชิลี": "Chile",
    "อาร์เจนติน่า": "Argentina", "อาร์เจนตินา": "Argentina", "ออสเตรเลีย": "Australia",
    "นิวซีแลนด์": "New Zealand", "อเมริกา": "USA", "โปรตุเกส": "Portugal",
    "เยอรมัน": "Germany", "แอฟริกาใต้": "South Africa", "ฮังการี": "Hungary",
}


def parse(obj):
    w = wc.common_wine(obj, KEY)
    blob = wc.text_blob(obj)
    w.wine_type = N.canonical_wine_type(wc.categories(obj), text=blob)
    w.vintage = N.parse_vintage(w.name)
    w.size_ml = N.parse_size_ml(w.name)
    for th, en in _THAI_COUNTRY.items():
        if th in blob:
            w.country = en
            break
    return w


def scrape(session=None):
    session = session or PoliteSession()
    objs = wc.fetch_all(session, CFG["base"], CFG["products_path"], CFG["params"])
    return [parse(o) for o in objs]
