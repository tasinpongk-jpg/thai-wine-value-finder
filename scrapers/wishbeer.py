"""Wishbeer — Shopify collection products.json. Attributes live in tags + title."""
from __future__ import annotations

from sources import SOURCES
from scrapers.base import PoliteSession, strip_html
from enrich import normalize as N
from enrich.critic_scores import extract_critic_scores
from models import Wine

KEY = "wishbeer"
CFG = SOURCES[KEY]


def _tag(tags, prefix):
    pl = prefix.lower() + ":"
    for t in tags or []:
        if str(t).lower().startswith(pl):
            return str(t).split(":", 1)[1].strip()
    return None


def parse(obj):
    title = N.clean_text(obj.get("title"))
    tags = obj.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    variants = obj.get("variants") or [{}]
    price = N.parse_price_text(variants[0].get("price"))
    imgs = obj.get("images") or []
    handle = obj.get("handle")
    wtype = _tag(tags, "Type")
    return Wine(
        source=KEY,
        source_id=str(obj.get("id") or handle or title),
        name=title,
        price_thb=price,
        wine_type=N.canonical_wine_type([wtype] if wtype else [], text=title),
        vintage=N.parse_vintage(title),
        size_ml=N.parse_size_ml(title),
        country=_tag(tags, "Country"),
        region=_tag(tags, "Region"),
        grape=_tag(tags, "Grape"),
        url=(CFG["base"] + "/products/" + handle) if handle else None,
        image=imgs[0].get("src") if imgs else None,
        critic_scores=extract_critic_scores(title + " " + strip_html(obj.get("body_html"))),
        producer=obj.get("vendor") or None,
        description=N.short_desc(strip_html(obj.get("body_html"))),
    )


def scrape(session=None):
    session = session or PoliteSession()
    out, page = [], 1
    limit = CFG["params"]["limit"]
    while page <= 20:
        data = session.get_json(CFG["base"] + CFG["products_path"],
                                dict(CFG["params"], page=page))
        prods = data.get("products") if isinstance(data, dict) else None
        if not prods:
            break
        out.extend(parse(p) for p in prods)
        if len(prods) < limit:
            break
        page += 1
    return out
