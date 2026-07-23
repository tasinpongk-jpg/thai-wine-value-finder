import math

from enrich import value as V
from models import Wine


# ---- quality -----------------------------------------------------------
def test_quality_prefers_vivino():
    assert V.quality_from_inputs(vivino_rating=4.5, critic_best=90) == 0.9


def test_quality_from_critic_when_no_vivino():
    # 90 pts -> (90-80)/20 = 0.5
    assert V.quality_from_inputs(vivino_rating=None, critic_best=90) == 0.5


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


def test_value_score_without_quality_ranks_lower():
    # no quality -> only pe + gap contribute (not reweighted up)
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
