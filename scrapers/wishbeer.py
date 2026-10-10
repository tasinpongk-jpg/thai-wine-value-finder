"""Wishbeer — Shopify collection products.json. Attributes live in tags + title."""
from __future__ import annotations

from sources import SOURCES
from scrapers.base import PoliteSession, strip_html, warn_page_cap
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


def _variant_size(v):
    return N.parse_size_ml(" ".join(str(v.get(k) or "") for k in
                                    ("title", "option1", "option2", "option3")))


def pick_variant(variants, title=""):
    """Prefer an available 750 ml variant, then any available one, then the first.

    Size comes from the variant's own title/options, falling back to the product
    title for single-size products ("Default Title").
    """
    variants = [v for v in (variants or []) if isinstance(v, dict)]
    if not variants:
        return {}
    title_size = N.parse_size_ml(title)

    def size(v):
        return _variant_size(v) or title_size

    available = [v for v in variants if v.get("available") is not False]
    for v in available:
        if size(v) == 750:
            return v
    if available:
        return available[0]
    return variants[0]


def is_available(obj) -> bool:
    """False only when every variant is explicitly unavailable."""
    variants = [v for v in (obj.get("variants") or []) if isinstance(v, dict)]
    if not variants:
        return True
    return any(v.get("available") is not False for v in variants)


def parse(obj):
    title = N.clean_text(obj.get("title"))
    tags = obj.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    variant = pick_variant(obj.get("variants"), title)
    price = N.parse_price_text(variant.get("price"))
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
        size_ml=_variant_size(variant) or N.parse_size_ml(title),
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
    out, page, max_pages = [], 1, 20
    limit = CFG["params"]["limit"]
    while True:
        if page > max_pages:
            warn_page_cap(KEY, max_pages)
            break
        data = session.get_json(CFG["base"] + CFG["products_path"],
                                dict(CFG["params"], page=page))
        prods = data.get("products") if isinstance(data, dict) else None
        if not prods:
            break
        out.extend(parse(p) for p in prods if is_available(p))
        if len(prods) < limit:
            break
        page += 1
    return out
