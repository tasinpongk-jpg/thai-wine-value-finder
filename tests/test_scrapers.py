"""Fixture-based parser tests. Fixtures are small real API responses captured
2026-06-24 (see tests/fixtures/). These test the pure parse() functions offline."""
import json
import os

from models import WINE_TYPES
from scrapers import winedutyfree, spirithouse, wishbeer
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


# ---- Wine Store Asia: catalog filtering + sale prices ------------------------
from datetime import date  # noqa: E402

_TREE = {
    "id": 2, "is_active": True, "children_data": [
        {"id": 3, "name": "Wine", "is_active": True, "children_data": [
            {"id": 37, "name": "France", "is_active": True, "children_data": []}]},
        {"id": 62, "name": "All Wine", "is_active": False, "children_data": []},
        {"id": 75, "name": "USA (California)", "is_active": False, "children_data": [
            {"id": 85, "name": "Kendall Jackson", "is_active": True,
             "children_data": []}]},
        {"id": 19, "name": "Top Seller", "is_active": True, "children_data": []},
    ]}


def _wsa_item(price=900, cats=("3", "37"), status=1, **attrs):
    ca = [{"attribute_code": "wine_type", "value": "17"},
          {"attribute_code": "category_ids", "value": list(cats)}]
    ca += [{"attribute_code": k, "value": v} for k, v in attrs.items()]
    return {"sku": "X1", "name": "Test Wine", "price": price, "status": status,
            "custom_attributes": ca}


def test_winestoreasia_category_flags_inherit_inactive_parent():
    active, inactive = wsa.category_flags(_TREE)
    assert {"2", "3", "37", "19"} <= active
    assert {"62", "75", "85"} <= inactive   # 85 is active but its parent isn't


def test_winestoreasia_drops_sgd_priced_singapore_range():
    active, inactive = wsa.category_flags(_TREE)
    thai = _wsa_item(900, cats=("3", "37"))
    # real example: Villa Sandi Cabernet Sauvignon (-sg) price 38, cats 62/89 + Top Seller
    singapore = _wsa_item(38, cats=("12", "19", "62", "70", "89"))
    disabled = _wsa_item(1120, cats=("3",), status=2)
    assert wsa.is_listed(thai, active, inactive)
    assert not wsa.is_listed(singapore, active, inactive)
    assert not wsa.is_listed(disabled, active, inactive)


def test_winestoreasia_without_category_tree_only_checks_status():
    assert wsa.is_listed(_wsa_item(), set(), set())
    assert not wsa.is_listed(_wsa_item(status=2), set(), set())


def test_winestoreasia_special_price_open_ended_applies():
    item = _wsa_item(570, special_price="460.0000",
                     special_from_date="2025-02-24 00:00:00")
    assert wsa.effective_price(item, today=date(2026, 10, 10)) == 460


def test_winestoreasia_special_price_respects_window():
    expired = _wsa_item(800, special_price="540.0000",
                        special_from_date="2020-11-02 00:00:00",
                        special_to_date="2020-12-05 00:00:00")
    future = _wsa_item(800, special_price="540.0000",
                       special_from_date="2027-01-01 00:00:00")
    last_day = _wsa_item(800, special_price="540.0000",
                         special_to_date="2026-10-10 00:00:00")
    today = date(2026, 10, 10)
    assert wsa.effective_price(expired, today=today) == 800
    assert wsa.effective_price(future, today=today) == 800
    assert wsa.effective_price(last_day, today=today) == 540


def test_winestoreasia_special_price_ignored_when_not_lower():
    item = _wsa_item(800, special_price="900.0000")
    assert wsa.effective_price(item, today=date(2026, 10, 10)) == 800


def test_winestoreasia_parse_uses_effective_price_and_name_size():
    maps = load("winestoreasia_attrs")
    item = _wsa_item(800, special_price="600", wine_bottle_size="372")  # "750 ml"
    item["name"] = "Test Wine Half Bottle 375ml"
    w = wsa.parse(item, maps, today=date(2026, 10, 10))
    assert w.price_thb == 600
    assert w.size_ml == 375


# ---- size from attributes / names ----------------------------------------
def _wc_obj(name, attrs):
    return {"id": 1, "name": name, "prices": {"price": "99000", "currency_minor_unit": 2},
            "attributes": [{"name": n, "taxonomy": t, "terms": [{"name": v}]}
                           for n, t, v in attrs]}


def test_winedutyfree_reads_thai_size_type_and_country_attributes():
    obj = _wc_obj("ไวน์แดง Robert Mondavi Private Selection Merlot", [
        ("ขนาดบรรจุ", "pa_bottle-size", "750 มล."),
        ("ประเภทไวน์", "pa_wine-type", "WHITE WINE"),
        ("ประเทศที่ผลิต", "pa_country", "USA"),
        ("แอลกอฮอล์", "pa_alcohol", "13.50%")])
    w = winedutyfree.parse(obj)
    assert w.size_ml == 750
    assert w.wine_type == "White"     # explicit attribute beats the name's colour word
    assert w.country == "USA"
    assert w.alcohol == "13.50%"


def test_winedutyfree_size_from_thai_name():
    w = winedutyfree.parse(_wc_obj("ไวน์แดง Penfolds Bin 2 375 มล.", []))
    assert w.size_ml == 375


def test_spirithouse_name_size_beats_volume_attribute():
    obj = _wc_obj("Astoria Butterfly Prosecco Extra Dry (375ml)",
                  [("Volume", "pa_volume", "750 ml")])
    assert spirithouse.parse(obj).size_ml == 375


# ---- stock / variants / attribute maps / page caps ---------------------------
import pytest  # noqa: E402

from scrapers import woocommerce as wc  # noqa: E402


def test_woocommerce_out_of_stock_filtered():
    objs = [dict(_wc_obj("In", []), is_in_stock=True),
            dict(_wc_obj("Out", []), id=2, is_in_stock=False),
            dict(_wc_obj("Unknown", []), id=3)]
    assert [wc.in_stock(o) for o in objs] == [True, False, True]


def test_wishbeer_picks_available_750_variant():
    variants = [
        {"title": "375ml", "price": "600.00", "available": True},
        {"title": "750ml", "price": "1,100.00", "available": False},
        {"title": "75cl", "price": "1,150.00", "available": True},
        {"title": "1.5L", "price": "2,300.00", "available": True},
    ]
    assert wishbeer.pick_variant(variants)["price"] == "1,150.00"


def test_wishbeer_falls_back_to_any_available_then_first():
    v = [{"title": "375ml", "price": "1", "available": False},
         {"title": "1.5L", "price": "2", "available": True}]
    assert wishbeer.pick_variant(v)["price"] == "2"
    v = [{"title": "A", "price": "1", "available": False},
         {"title": "B", "price": "2", "available": False}]
    assert wishbeer.pick_variant(v)["price"] == "1"
    assert wishbeer.pick_variant([]) == {}


def test_wishbeer_default_title_uses_product_title_size():
    v = [{"title": "Default Title", "price": "900.00", "available": True}]
    assert wishbeer.pick_variant(v, "Some Wine 750ml")["price"] == "900.00"


def test_wishbeer_parse_uses_chosen_variant_price_and_size():
    obj = {"id": 1, "title": "Test Wine", "tags": [], "variants": [
        {"title": "375ml", "price": "600.00", "available": True},
        {"title": "750ml", "price": "1,100.00", "available": True}]}
    w = wishbeer.parse(obj)
    assert w.price_thb == 1100.0
    assert w.size_ml == 750


def test_wishbeer_unavailable_products_skipped():
    assert wishbeer.is_available({"variants": [{"available": True}]})
    assert not wishbeer.is_available({"variants": [{"available": False}]})
    assert wishbeer.is_available({"variants": []})


class _Session:
    def __init__(self, fail_on=None, pages=None):
        self.fail_on, self.pages, self.calls = fail_on, pages or {}, []

    def get_json(self, url, params=None):
        self.calls.append(url)
        if self.fail_on and self.fail_on in url:
            raise RuntimeError("HTTP 503")
        return self.pages.get(url, {"options": [{"value": "17", "label": "Red Wine"}]})


def test_winestoreasia_attr_map_failure_fails_the_shop(capsys):
    with pytest.raises(wsa.AttributeMapError):
        wsa.fetch_attr_maps(_Session(fail_on="wine_body"))
    assert "wine_body" in capsys.readouterr().out


def test_winestoreasia_empty_wine_type_map_fails():
    s = _Session()
    s.pages[wsa.CFG["base"] + "/rest/V1/products/attributes/wine_type"] = {"options": []}
    with pytest.raises(wsa.AttributeMapError):
        wsa.fetch_attr_maps(s)


def test_woocommerce_page_cap_warns(capsys):
    class Full:
        def get_json(self, url, params=None):
            return [{"id": i} for i in range(params["per_page"])]
    out = wc.fetch_all(Full(), "https://shop", "/p", {"per_page": 2}, max_pages=3)
    assert len(out) == 6
    assert "safety cap" in capsys.readouterr().out


def test_wishbeer_page_cap_warns(capsys, monkeypatch):
    class Full:
        def get_json(self, url, params=None):
            return {"products": [{"id": i, "title": f"w{i}", "variants": [
                {"price": "900", "available": True}]} for i in range(params["limit"])]}
    monkeypatch.setitem(wishbeer.CFG["params"], "limit", 2)
    out = wishbeer.scrape(Full())
    assert len(out) == 40
    assert "safety cap" in capsys.readouterr().out
