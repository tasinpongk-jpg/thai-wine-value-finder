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
    amap = wc.attr_map(obj)
    # pa_* attributes (on most products) are "RED WINE", "750 ML", "France"...;
    # Thai labels like "750 มล." are handled by the size parser too.
    wtype = wc.first_attr(amap, "pa_wine-type", "ประเภทไวน์")
    w.wine_type = N.canonical_wine_type(
        ([wtype] if wtype else []) + wc.categories(obj), text=blob)
    w.vintage = N.parse_vintage(w.name)
    w.size_ml = N.resolve_size_ml(
        w.name, wc.first_attr(amap, "pa_bottle-size", "ขนาดบรรจุ"))
    w.alcohol = wc.first_attr(amap, "pa_alcohol", "แอลกอฮอล์")
    w.country = wc.first_attr(amap, "pa_country", "ประเทศที่ผลิต")
    if not w.country:
        for th, en in _THAI_COUNTRY.items():
            if th in blob:
                w.country = en
                break
    return w


def scrape(session=None):
    session = session or PoliteSession()
    objs = wc.fetch_all(session, CFG["base"], CFG["products_path"], CFG["params"])
    return [parse(o) for o in objs if wc.in_stock(o)]
