from enrich.match import assign_match_groups
from models import Wine


def W(name, src, vintage=None, size=750, price=1000):
    return Wine(source=src, source_id=f"{name}-{src}", name=name,
                vintage=vintage, size_ml=size, price_thb=price)


def test_same_wine_across_sites_grouped():
    a, b = W("Penfolds Bin 389", "s1", 2021), W("Penfolds Bin 389", "s2", 2021)
    assign_match_groups([a, b])
    assert a.match_group == b.match_group


def test_different_vintage_not_grouped():
    a, b = W("Penfolds Bin 389", "s1", 2021), W("Penfolds Bin 389", "s2", 2020)
    assign_match_groups([a, b])
    assert a.match_group != b.match_group


def test_unrelated_not_grouped():
    a, b = W("Penfolds Bin 389", "s1", 2021), W("Trapiche Malbec", "s2", 2021)
    assign_match_groups([a, b])
    assert a.match_group != b.match_group


def test_size_mismatch_not_grouped():
    a = W("Penfolds Bin 389", "s1", 2021, size=750)
    b = W("Penfolds Bin 389", "s2", 2021, size=1500)
    assign_match_groups([a, b])
    assert a.match_group != b.match_group


def test_fuzzy_extra_words_grouped():
    a = W("Penfolds Bin 389 Cabernet Shiraz", "s1", 2021)
    b = W("Penfolds Bin 389", "s2", 2021)
    assign_match_groups([a, b])
    assert a.match_group == b.match_group


def test_every_wine_gets_group_id():
    a, b = W("Alpha", "s1"), W("Beta", "s2")
    assign_match_groups([a, b])
    assert a.match_group is not None
    assert b.match_group is not None


def test_none_vintage_does_not_bridge_distinct_vintages():
    # a no-vintage listing must not glue 2014 and 2015 into one group
    a = W("Cono Sur Ocio Pinot Noir", "s1", vintage=None)
    b = W("Cono Sur Ocio Pinot Noir", "s2", vintage=2014)
    c = W("Cono Sur Ocio Pinot Noir", "s3", vintage=2015)
    assign_match_groups([a, b, c])
    assert b.match_group != c.match_group


def test_three_listings_two_match():
    a = W("Trapiche Gran Medalla Malbec", "s1", 2019)
    b = W("Trapiche Gran Medalla Malbec", "s2", 2019)
    c = W("Allegrini Palazzo della Torre", "s3", 2021)
    assign_match_groups([a, b, c])
    assert a.match_group == b.match_group
    assert c.match_group != a.match_group
