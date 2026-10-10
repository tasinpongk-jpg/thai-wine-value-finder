"""Wine Store Asia — Magento 2 REST API. Wine attributes are dropdown IDs that
must be resolved to labels via /rest/V1/products/attributes/{code}.

Pricing notes (verified live 2026-10-10):
- Every store view ("th", "default", "sgd") has THB as its base currency and the
  REST ``price`` is identical across views, so the store code alone doesn't fix
  anything. The bad prices come from ~100 Singapore SKUs (url keys ending in
  ``-sg``) whose ``price`` holds SGD amounts (e.g. 38 for a ฿900 wine). They live
  only in the disabled "All Wine" category tree, so we drop products that are in
  any inactive category, or that aren't in an active one, or are disabled.
- ``special_price`` (with optional ``special_from_date``/``special_to_date``) is
  the shop's sale price and is applied when active and lower than ``price``.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

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


BANGKOK = ZoneInfo("Asia/Bangkok")


def fetch_category_flags(session):
    """Return (active_ids, inactive_ids) as string sets from the category tree.

    A category counts as inactive when it, or any ancestor, has is_active=false.
    On failure both sets are empty and category filtering is skipped (the
    price sanity check in daily_refresh still applies).
    """
    try:
        tree = session.get_json(CFG["base"] + CFG["categories_path"])
    except Exception as e:  # noqa: BLE001 - degrade, but say so
        print(f"  winestoreasia: category tree unavailable ({type(e).__name__}); "
              "not filtering by category")
        return set(), set()
    return category_flags(tree)


def category_flags(tree):
    active, inactive = set(), set()

    def walk(node, parent_active):
        if not isinstance(node, dict):
            return
        is_active = bool(node.get("is_active", True)) and parent_active
        if node.get("id") is not None:
            (active if is_active else inactive).add(str(node["id"]))
        for child in node.get("children_data") or []:
            walk(child, is_active)

    walk(tree, True)
    return active, inactive


def is_listed(item, active=None, inactive=None):
    """Enabled product that's sold through the (active) Thai catalog."""
    if item.get("status") not in (None, 1, "1"):
        return False
    if not active and not inactive:
        return True
    cats = {str(c) for c in (_ca(item).get("category_ids") or [])}
    return bool(cats & active) and not (cats & inactive)


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace(" ", "T")).date()
    except ValueError:
        return None


def effective_price(item, today=None):
    """Regular price, or the active special_price when it's lower."""
    price = _to_float(item.get("price"))
    ca = _ca(item)
    special = _to_float(ca.get("special_price"))
    if special is None or special <= 0 or (price is not None and special >= price):
        return price
    today = today or datetime.now(BANGKOK).date()
    start, end = _parse_dt(ca.get("special_from_date")), _parse_dt(ca.get("special_to_date"))
    if start and today < start:
        return price
    if end and today > end:
        return price
    return special


def _ca(item):
    return {a.get("attribute_code"): a.get("value")
            for a in (item.get("custom_attributes") or [])}


def _label(maps, code, val):
    if val in (None, ""):
        return None
    return maps.get(code, {}).get(str(val))


def is_wine(item):
    return _ca(item).get("wine_type") not in (None, "")


def parse(item, maps, today: date | None = None):
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
        price_thb=effective_price(item, today),
        wine_type=N.canonical_wine_type([wtype] if wtype else [], text=name),
        vintage=N.parse_vintage(ca.get("vintage")) or N.parse_vintage(name),
        size_ml=N.resolve_size_ml(
            name, _label(maps, "wine_bottle_size", ca.get("wine_bottle_size"))),
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
    active, inactive = fetch_category_flags(session)
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
    today = datetime.now(BANGKOK).date()
    return [parse(it, maps, today) for it in items
            if is_wine(it) and is_listed(it, active, inactive)]
