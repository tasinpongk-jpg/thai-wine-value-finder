"""Wine Store Asia — Magento 2 REST API. Wine attributes are dropdown IDs that
must be resolved to labels via /rest/V1/products/attributes/{code}."""
from __future__ import annotations

from sources import SOURCES
from scrapers.base import PoliteSession, strip_html
from scrapers.woocommerce import _to_float
from enrich import normalize as N
from enrich.critic_scores import extract_critic_scores
from models import Wine

KEY = "winestoreasia"
CFG = SOURCES[KEY]

ATTR_CODES = ["wine_type", "wine_bottle_size", "country",
              "wine_province_area", "wine_grape_varieties",
              "wine_body", "wine_alcohol_level", "wine_brand"]

_ISO = {"AR": "Argentina", "AU": "Australia", "CL": "Chile", "FR": "France",
        "IT": "Italy", "ES": "Spain", "US": "USA", "NZ": "New Zealand",
        "DE": "Germany", "PT": "Portugal", "ZA": "South Africa"}


def fetch_attr_maps(session):
    maps = {}
    for code in ATTR_CODES:
        try:
            data = session.get_json(CFG["base"] + f"/rest/V1/products/attributes/{code}")
            opts = data.get("options") or []
            maps[code] = {str(o.get("value")): o.get("label")
                          for o in opts if o.get("value") not in (None, "")}
        except Exception:
            maps[code] = {}
    return maps


def _ca(item):
    return {a.get("attribute_code"): a.get("value")
            for a in (item.get("custom_attributes") or [])}


def _label(maps, code, val):
    if val in (None, ""):
        return None
    return maps.get(code, {}).get(str(val))


def is_wine(item):
    return _ca(item).get("wine_type") not in (None, "")


def parse(item, maps):
    ca = _ca(item)
    name = N.clean_text(item.get("name"))
    img = ca.get("image") or ca.get("small_image")
    image = (CFG["base"] + "/pub/media/catalog/product" + img) if img else None
    wtype = _label(maps, "wine_type", ca.get("wine_type"))
    blob = " ".join(filter(None, [
        name, strip_html(ca.get("short_description")),
        strip_html(ca.get("description")), strip_html(ca.get("wine_tasting_note"))]))
    url_key = ca.get("url_key")
    return Wine(
        source=KEY,
        source_id=str(item.get("sku") or item.get("id") or name),
        name=name,
        price_thb=_to_float(item.get("price")),
        wine_type=N.canonical_wine_type([wtype] if wtype else [], text=name),
        vintage=N.parse_vintage(ca.get("vintage")) or N.parse_vintage(name),
        size_ml=N.parse_size_ml(
            _label(maps, "wine_bottle_size", ca.get("wine_bottle_size")) or name),
        country=(_label(maps, "country", ca.get("country"))
                 or _ISO.get(ca.get("country_of_manufacture"))),
        region=_label(maps, "wine_province_area", ca.get("wine_province_area")),
        grape=_label(maps, "wine_grape_varieties", ca.get("wine_grape_varieties")),
        url=(CFG["base"] + "/" + url_key + ".html") if url_key else None,
        image=image,
        critic_scores=extract_critic_scores(blob),
        producer=_label(maps, "wine_brand", ca.get("wine_brand")),
        body=_label(maps, "wine_body", ca.get("wine_body")),
        alcohol=_label(maps, "wine_alcohol_level", ca.get("wine_alcohol_level")),
        nose=N.short_desc(strip_html(ca.get("aroma")), 240),
        palate=N.short_desc(strip_html(ca.get("palate")), 240),
        appearance=N.short_desc(strip_html(ca.get("wine_appearance")), 200),
        description=N.short_desc(strip_html(ca.get("short_description"))),
    )


def scrape(session=None):
    session = session or PoliteSession()
    maps = fetch_attr_maps(session)
    page_size = CFG["params"]["searchCriteria[pageSize]"]
    items, page = [], 1
    while page <= 30:
        params = dict(CFG["params"])
        params["searchCriteria[currentPage]"] = page
        data = session.get_json(CFG["base"] + CFG["products_path"], params)
        batch = data.get("items") if isinstance(data, dict) else None
        if not batch:
            break
        items.extend(batch)
        if page * page_size >= (data.get("total_count") or 0):
            break
        page += 1
    return [parse(it, maps) for it in items if is_wine(it)]
