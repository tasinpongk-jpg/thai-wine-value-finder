"""Fixture-based parser tests. Fixtures are small real API responses captured
2026-06-24 (see tests/fixtures/). These test the pure parse() functions offline."""
import json
import os

from models import WINE_TYPES
from scrapers import winedutyfree, wineplus, spirithouse, wishbeer
from scrapers import winestoreasia as wsa

FX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FX, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _sane(wines, key):
    assert wines, f"{key}: no wines parsed"
    for w in wines:
        assert w.source == key
        assert w.name and w.name.strip()
        assert w.price_thb and w.price_thb > 0, f"{key}: bad price {w.name}"
        assert w.wine_type in WINE_TYPES


# ---- WooCommerce sites -------------------------------------------------
def test_winedutyfree_parses():
    wines = [winedutyfree.parse(o) for o in load("winedutyfree")]
    _sane(wines, "winedutyfree")
    # type & country come from the embedded Thai text
    assert wines[0].wine_type == "Red"
    assert wines[0].country == "Italy"


def test_wineplus_parses_and_filters_nonwine():
    raw = load("wineplus")
    wines = [wineplus.parse(o) for o in raw if wineplus._is_wine(o)]
    _sane(wines, "wineplus")
    first = wines[0]
    assert first.wine_type == "White"
    assert first.country == "New Zealand"
    assert first.size_ml == 750


def test_spirithouse_uses_site_vivino_rating():
    wines = [spirithouse.parse(o) for o in load("spirithouse")]
    _sane(wines, "spirithouse")
    w = wines[0]
    assert w.vivino_rating == 4.6
    assert w.vivino_source == "site"
    assert w.vintage == 2019
    assert w.country == "USA"


def test_wishbeer_parses_tags_and_title():
    wines = [wishbeer.parse(p) for p in load("wishbeer")["products"]]
    _sane(wines, "wishbeer")
    assert wines[0].wine_type == "Sparkling"
    # vintage parsed out of the title
    by_vintage = {w.vintage for w in wines}
    assert 2019 in by_vintage or 2020 in by_vintage


def test_winestoreasia_resolves_attribute_ids():
    maps = load("winestoreasia_attrs")
    items = load("winestoreasia")["items"]
    wines = [wsa.parse(it, maps) for it in items if wsa.is_wine(it)]
    _sane(wines, "winestoreasia")
    w = wines[0]
    assert w.country == "Argentina"
    assert w.vintage == 2013
    assert w.size_ml == 750
