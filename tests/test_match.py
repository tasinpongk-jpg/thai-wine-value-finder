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


# --- the vectorized matcher must give exactly the old greedy result -------------

def _reference_assign(wines, threshold=90):
    """The original O(n * members) greedy implementation, kept as an oracle."""
    from rapidfuzz import fuzz

    from enrich.match import _compatible
    from enrich.normalize import normalize_name
    norms = [normalize_name(w.name) for w in wines]
    clusters = []
    low = [False] * len(wines)
    for i, w in enumerate(wines):
        placed = False
        for c in clusters:
            if any(not _compatible(w, wines[m]) for m in c["members"]):
                continue
            if not norms[i] or not c["rep"]:
                continue
            if fuzz.token_set_ratio(norms[i], c["rep"]) >= threshold:
                if fuzz.token_sort_ratio(norms[i], c["rep"]) < threshold:
                    low[i] = True
                c["members"].append(i)
                placed = True
                break
        if not placed:
            clusters.append({"rep": norms[i], "members": [i]})
    groups = [None] * len(wines)
    for gid, c in enumerate(clusters):
        for idx in c["members"]:
            groups[idx] = gid
            if len(c["members"]) == 1:
                low[idx] = False
    return groups, low


def _varied_catalog(n, seed):
    import random
    rng = random.Random(seed)
    producers = ["Penfolds", "Trapiche", "Chateau Margaux", "Yellow Tail", "Torres",
                 "Cloudy Bay", "Mouton Cadet", "Casillero del Diablo", "Jacob's Creek"]
    cuvees = ["Bin 389", "Malbec", "Reserve", "Sauvignon Blanc", "Shiraz Cabernet",
              "Gran Reserva", "Pinot Noir", "Brut", "Rosé", ""]
    extras = ["", "", "Red Wine", "750ml", "Limited Edition", "Magnum", "Gift Box"]
    out = []
    for i in range(n):
        name = " ".join(p for p in (rng.choice(producers), rng.choice(cuvees),
                                    rng.choice(extras)) if p)
        if rng.random() < 0.15:          # word-order shuffles -> low confidence joins
            parts = name.split()
            rng.shuffle(parts)
            name = " ".join(parts)
        if rng.random() < 0.03:
            name = rng.choice(["", "   ", "750ml"])   # empty after normalization
        out.append(Wine(source=f"s{i % 5}", source_id=str(i), name=name,
                        vintage=rng.choice([None, None, 2019, 2020, 2021]),
                        size_ml=rng.choice([None, 750, 750, 750, 375, 1500])))
    return out


def test_vectorized_matcher_matches_reference_greedy():
    import enrich.match as m
    for seed in range(4):
        wines = _varied_catalog(700, seed)
        expected = _reference_assign(wines)
        assign_match_groups(wines)
        assert [w.match_group for w in wines] == expected[0]
        assert [bool(w.match_low_confidence) for w in wines] == expected[1]
    # crossing score-matrix block boundaries must not change anything
    wines = _varied_catalog(300, 99)
    expected = _reference_assign(wines)
    old = m._BLOCK_ROWS
    try:
        m._BLOCK_ROWS = 7
        assign_match_groups(wines)
    finally:
        m._BLOCK_ROWS = old
    assert [w.match_group for w in wines] == expected[0]
    assert [bool(w.match_low_confidence) for w in wines] == expected[1]


def test_no_vintage_listing_cannot_bridge_two_vintages():
    a = W("Penfolds Bin 389", "s1", 2020)
    b = W("Penfolds Bin 389", "s2", None)
    c = W("Penfolds Bin 389", "s3", 2021)
    assign_match_groups([a, b, c])
    assert a.match_group == b.match_group != c.match_group


def test_empty_names_never_group():
    a, b = W("", "s1"), W("", "s2")
    assign_match_groups([a, b])
    assert a.match_group != b.match_group
    assert assign_match_groups([]) == []
