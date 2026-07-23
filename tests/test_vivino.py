import json

from enrich import vivino
from models import Wine


def test_parse_finds_rating_in_nested_structure():
    data = {"explore_vintage": {"records": [
        {"vintage": {"wine": {"statistics":
            {"ratings_average": 4.2, "ratings_count": 1500}}}}]}}
    assert vivino.parse_vivino_response(data) == {"rating": 4.2, "count": 1500}


def test_parse_returns_none_when_no_rating():
    assert vivino.parse_vivino_response({"foo": "bar"}) is None


def test_parse_ignores_zero_rating():
    assert vivino.parse_vivino_response({"ratings_average": 0, "ratings_count": 0}) is None


def test_enrich_uses_cache_and_never_hits_network(tmp_path):
    cache = tmp_path / "v.json"
    w = Wine(source="s", source_id="1", name="Penfolds Bin 389", vintage=2021)
    key = vivino.cache_key(w.name, w.vintage)
    cache.write_text(json.dumps({key: {"rating": 4.3, "count": 99}}), encoding="utf-8")

    class Boom:
        def __getattr__(self, _):
            raise AssertionError("network must not be used when cached")

    hits = vivino.enrich_wines([w], session=Boom(), cache_path=str(cache), log=lambda *_: None)
    assert hits == 1
    assert w.vivino_rating == 4.3
    assert w.vivino_count == 99
    assert w.vivino_source == "lookup"


def test_enrich_skips_wines_that_already_have_rating(tmp_path):
    cache = tmp_path / "v.json"
    w = Wine(source="s", source_id="1", name="Already rated",
             vivino_rating=4.5, vivino_source="site")

    class Boom:
        def __getattr__(self, _):
            raise AssertionError("must not look up a wine that already has a rating")

    hits = vivino.enrich_wines([w], session=Boom(), cache_path=str(cache), log=lambda *_: None)
    assert hits == 0
    assert w.vivino_rating == 4.5
