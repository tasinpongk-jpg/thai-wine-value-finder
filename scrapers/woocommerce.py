"""Shared helpers for the three WooCommerce Store-API sites
(winedutyfree, wineplus, spirithouse)."""
from __future__ import annotations

from enrich import normalize as N
from enrich.critic_scores import extract_critic_scores
from scrapers.base import strip_html
from models import Wine


def attr_map(obj) -> dict:
    """{lowercased taxonomy or attribute name -> [term names]}."""
    out = {}
    for a in obj.get("attributes") or []:
        terms = [t.get("name") for t in (a.get("terms") or []) if t.get("name")]
        for key in (a.get("taxonomy"), a.get("name")):
            if key:
                out[str(key).strip().lower()] = terms
    return out


def first_attr(amap: dict, *keys):
    for k in keys:
        terms = amap.get(k.lower())
        if terms:
            return terms[0]
    return None


def all_attr(amap: dict, *keys):
    for k in keys:
        terms = amap.get(k.lower())
        if terms:
            return terms
    return []


def price_thb(obj):
    p = obj.get("prices") or {}
    return N.parse_wc_price(p.get("price"), p.get("currency_minor_unit", 2))


def categories(obj):
    return [c.get("name") for c in (obj.get("categories") or []) if c.get("name")]


def text_blob(obj):
    return " ".join([obj.get("name") or "",
                     strip_html(obj.get("short_description")),
                     strip_html(obj.get("description"))])


def _to_float(x):
    try:
        v = float(x)
        return v if v else None
    except (TypeError, ValueError):
        return None


def common_wine(obj, source_key) -> Wine:
    """Fill the fields every WooCommerce product shares; caller refines the rest."""
    name = N.clean_text(obj.get("name"))
    imgs = obj.get("images") or []
    return Wine(
        source=source_key,
        source_id=str(obj.get("id") or obj.get("sku") or name),
        name=name,
        price_thb=price_thb(obj),
        url=obj.get("permalink"),
        image=imgs[0].get("src") if imgs else None,
        description=N.short_desc(strip_html(obj.get("description"))
                                 or strip_html(obj.get("short_description"))),
        critic_scores=extract_critic_scores(text_blob(obj)),
        review_rating=_to_float(obj.get("average_rating")),
        review_count=obj.get("review_count") or None,
    )


def fetch_all(session, base, path, params, max_pages=80):
    """Paginate a WooCommerce Store-API endpoint until a short/empty page."""
    out, page = [], 1
    per_page = params.get("per_page", 100)
    while page <= max_pages:
        p = dict(params, page=page)
        batch = session.get_json(base + path, p)
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
    return out
