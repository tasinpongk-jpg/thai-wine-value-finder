from enrich import value as V
from models import Wine


# ---- quality (calibrated: Vivino stars -> points -> 0-1) -----------------
def test_vivino_to_points_calibration():
    assert V.vivino_to_points(3.5) == 86
    assert V.vivino_to_points(4.0) == 90
    assert V.vivino_to_points(4.5) == 94
    assert V.vivino_to_points(None) is None
    assert V.vivino_to_points(0) is None


def test_quality_same_scale_for_vivino_and_critic():
    # Vivino 4.0 and a 90-point critic score mean the same quality
    assert V.quality_from_inputs(4.0, None) == V.quality_from_inputs(None, 90)
    assert V.quality_from_inputs(None, 90) == round(10 / 15, 4)


def test_quality_blends_vivino_and_critic():
    # 4.5 stars = 94 pts; with a 90-pt critic score -> 92 pts -> (92-80)/15 = 0.8
    assert V.quality_from_inputs(vivino_rating=4.5, critic_best=90) == 0.8


def test_quality_from_critic_when_no_vivino():
    assert V.quality_from_inputs(vivino_rating=None, critic_best=95) == 1.0


def test_quality_critic_clamped():
    assert V.quality_from_inputs(None, 105) == 1.0
    assert V.quality_from_inputs(None, 70) == 0.0


def test_quality_none_when_no_signal():
    assert V.quality_from_inputs(None, None) is None


# ---- cross-site gap ----------------------------------------------------
def test_cross_site_gap_cheaper_listing():
    assert V.cross_site_gap(800, [800, 1000, 1200]) == 0.2  # median 1000


def test_cross_site_gap_not_cheapest_is_zero():
    assert V.cross_site_gap(1100, [800, 1000, 1200]) == 0.0


def test_cross_site_gap_single_listing_zero():
    assert V.cross_site_gap(800, [800]) == 0.0


# ---- normalize ---------------------------------------------------------
def test_minmax_normalize():
    assert V.minmax([1, 2, 3]) == [0.0, 0.5, 1.0]


def test_minmax_all_equal_returns_zeros():
    assert V.minmax([5, 5, 5]) == [0.0, 0.0, 0.0]


# ---- value score -------------------------------------------------------
def test_value_score_full():
    # 100*(0.45*0.9 + 0.35*0.5 + 0.20*0.2) = 62.0
    assert V.value_score(quality=0.9, price_efficiency=0.5, cross_site_gap=0.2) == 62.0


def test_value_score_none_quality_contributes_zero():
    assert V.value_score(quality=None, price_efficiency=1.0, cross_site_gap=0.0) == 35.0


# ---- integration: compute_scores over a dataset ------------------------
def test_compute_scores_sets_fields_and_ranks_value_buy_first():
    wines = [
        Wine(source="a", source_id="1", name="Cheap good", price_thb=500,
             vivino_rating=4.4),
        Wine(source="b", source_id="2", name="Pricey same quality", price_thb=2000,
             vivino_rating=4.4),
        Wine(source="c", source_id="3", name="No rating", price_thb=500),
    ]
    V.compute_scores(wines)
    for w in wines:
        assert w.value_score is not None
        assert 0 <= w.value_score <= 100
    cheap, pricey, norating = wines
    # same quality, cheaper -> better price efficiency -> higher value
    assert cheap.value_score > pricey.value_score
    # the rated cheap wine should beat the unrated one
    assert cheap.value_score > norating.value_score


# ---- bottle-size normalization ---------------------------------------------
def test_price_per_750():
    assert V.price_per_750(500, 375) == 1000
    assert V.price_per_750(3000, 1500) == 1500
    assert V.price_per_750(900, 750) == 900
    assert V.price_per_750(900, None) == 900      # unknown size: as listed
    assert V.price_per_750(None, 750) is None
    assert V.price_per_750(0, 750) is None


def test_half_bottle_not_favored_over_same_value_full_bottle():
    half = Wine(source="a", source_id="1", name="Half", price_thb=500,
                size_ml=375, vivino_rating=4.0)
    full = Wine(source="b", source_id="2", name="Full", price_thb=1000,
                size_ml=750, vivino_rating=4.0)
    other = Wine(source="c", source_id="3", name="Other", price_thb=3000,
                 size_ml=750, vivino_rating=4.2)
    V.compute_scores([half, full, other])
    # identical price per 750 ml and quality -> identical score
    assert half.price_efficiency == full.price_efficiency
    assert half.value_score == full.value_score


def test_cross_site_gap_compares_price_per_750():
    # same wine (group 1): 375 ml at 500 is NOT cheaper than 750 ml at 900
    half = Wine(source="a", source_id="1", name="X", price_thb=500, size_ml=375,
                match_group=1)
    full = Wine(source="b", source_id="2", name="X", price_thb=900, size_ml=750,
                match_group=1)
    V.compute_scores([half, full])
    assert half.cross_site_gap == 0.0
    assert full.cross_site_gap > 0.0


# ---- unrated wines: typical-for-type estimate --------------------------------
def _rated(i, stars, price, wtype="Red"):
    return Wine(source="a", source_id=str(i), name=f"r{i}", price_thb=price,
                vivino_rating=stars, wine_type=wtype)


def test_unrated_gets_estimate_but_quality_stays_none():
    wines = [_rated(i, 3.5 + 0.1 * i, 1000) for i in range(11)]
    unrated = Wine(source="b", source_id="u", name="Unrated", price_thb=600,
                   wine_type="Red")
    V.compute_scores(wines + [unrated])
    assert unrated.quality is None
    median_q = sorted(w.quality for w in wines)[5]
    assert unrated.quality_est == round(median_q * V.UNRATED_CONFIDENCE, 4)
    assert all(w.quality_est is None for w in wines)
    # it now competes: cheaper than every rated wine -> real price efficiency
    assert unrated.price_efficiency > 0
    assert unrated.value_score > 20


def test_unrated_ranked_by_price_within_type():
    wines = [_rated(i, 4.0, 1000) for i in range(3)]
    cheap = Wine(source="b", source_id="c", name="Cheap", price_thb=400, wine_type="Red")
    dear = Wine(source="b", source_id="d", name="Dear", price_thb=1600, wine_type="Red")
    half = Wine(source="b", source_id="h", name="Half", price_thb=300, size_ml=375,
                wine_type="Red")   # ฿600 per 750 ml
    V.compute_scores(wines + [cheap, dear, half])
    assert cheap.value_score > half.value_score > dear.value_score


def test_rated_beats_equally_priced_unrated_of_typical_quality():
    rated = [_rated(i, 4.0, 800) for i in range(3)]
    unrated = Wine(source="b", source_id="u", name="U", price_thb=800, wine_type="Red")
    V.compute_scores(rated + [unrated])
    assert rated[0].value_score > unrated.value_score


def test_type_prior_used_when_enough_rated_else_global():
    reds = [_rated(i, 4.4, 1000) for i in range(V.MIN_RATED_PER_TYPE)]
    whites = [_rated(100 + i, 3.6, 1000, "White") for i in range(2)]
    V.compute_scores(reds + whites)
    priors = V.unrated_priors(reds + whites)
    assert priors["Red"] == round(reds[0].quality * V.UNRATED_CONFIDENCE, 4)
    assert "White" not in priors          # too few -> falls back to global
    assert None in priors


def test_no_rated_wines_at_all_leaves_estimate_none():
    wines = [Wine(source="a", source_id="1", name="x", price_thb=500)]
    V.compute_scores(wines)
    assert wines[0].quality_est is None
    assert wines[0].value_score == 0.0


def test_zero_quality_is_a_real_rating_not_missing():
    # 80 critic points -> quality 0.0; must not be treated as "unrated"
    zero = Wine(source="a", source_id="z", name="Z", price_thb=500,
                critic_scores=[{"critic": "WS", "score": 80}])
    other = _rated(1, 4.2, 900)
    V.compute_scores([zero, other])
    assert zero.quality == 0.0
    assert zero.quality_est is None
