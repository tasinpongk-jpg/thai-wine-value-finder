"""Compute the 0-100 value score and its three visible components.

Ratings from different sources are first put on ONE calibrated scale ("points",
the familiar 100-point critic scale), then mapped to quality 0-1:

    Vivino stars -> points:  90 + (stars - 4.0) * 8   (3.5 -> 86, 4.0 -> 90, 4.5 -> 94)
    quality      = clamp((points - 80) / 15, 0, 1)    (80 -> 0, 90 -> 0.67, 95 -> 1)

When a wine has both a Vivino rating and critic scores, their points are averaged.

Unrated wines (most listings outside Spirit House) get an *estimated* quality:
the median quality of rated wines of the same type (or of all rated wines if
that type has too few), i.e. "assume a typical wine of its type", times a small
uncertainty discount (0.95). Their price efficiency is then computed exactly
like a rated wine's, so among unrated wines of a type the ranking is by price per
750 ml, and an unrated wine only beats a rated one when it's clearly cheaper.
The estimate is stored in ``quality_est``; ``quality`` stays None (so "has a
rating" filters still mean a real rating).
"""
from __future__ import annotations

import math
import statistics
from typing import Dict, List, Optional

from enrich.critic_scores import best_critic_score

WEIGHTS = (0.45, 0.35, 0.20)  # quality, price_efficiency, cross_site_gap
STANDARD_ML = 750
_MIN_ML, _MAX_ML = 50, 27000

# calibration (see module docstring)
VIVINO_PIVOT_STARS, VIVINO_PIVOT_POINTS, POINTS_PER_STAR = 4.0, 90.0, 8.0
QUALITY_FLOOR_POINTS, QUALITY_SPAN_POINTS = 80.0, 15.0
# unrated prior
UNRATED_PRIOR_PERCENTILE = 50
# small uncertainty discount, so a rated wine beats an equally priced unrated
# one of exactly typical quality
UNRATED_CONFIDENCE = 0.95
MIN_RATED_PER_TYPE = 10


def price_per_750(price: Optional[float], size_ml: Optional[int]) -> Optional[float]:
    """Price normalized to a standard 750 ml bottle (unchanged if size unknown)."""
    if not price or price <= 0:
        return None
    if size_ml and _MIN_ML <= size_ml <= _MAX_ML:
        return price * STANDARD_ML / size_ml
    return price


def vivino_to_points(stars: Optional[float]) -> Optional[float]:
    if stars is None or stars <= 0:
        return None
    return VIVINO_PIVOT_POINTS + (stars - VIVINO_PIVOT_STARS) * POINTS_PER_STAR


def points_to_quality(points: Optional[float]) -> Optional[float]:
    if points is None:
        return None
    return max(0.0, min(1.0, (points - QUALITY_FLOOR_POINTS) / QUALITY_SPAN_POINTS))


def quality_from_inputs(vivino_rating: Optional[float],
                        critic_best: Optional[int]) -> Optional[float]:
    """Calibrated 0-1 quality from Vivino stars and/or best critic points."""
    pts = [p for p in (vivino_to_points(vivino_rating),
                       float(critic_best) if critic_best is not None else None)
           if p is not None]
    if not pts:
        return None
    return round(points_to_quality(sum(pts) / len(pts)), 4)


def _percentile(values: List[float], pct: float) -> float:
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * pct / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def unrated_priors(wines) -> Dict[Optional[str], float]:
    """{wine_type -> conservative quality estimate}; key None is the global fallback."""
    by_type: Dict[Optional[str], List[float]] = {}
    for w in wines:
        if w.quality is not None:
            by_type.setdefault(w.wine_type, []).append(w.quality)
    everything = [q for qs in by_type.values() for q in qs]
    def prior(qs):
        return round(_percentile(qs, UNRATED_PRIOR_PERCENTILE) * UNRATED_CONFIDENCE, 4)

    priors = {None: prior(everything)} if everything else {}
    for t, qs in by_type.items():
        if len(qs) >= MIN_RATED_PER_TYPE:
            priors[t] = prior(qs)
    return priors


def cross_site_gap(price: float, group_prices: List[float]) -> float:
    """How far below the same-wine median this listing sits, 0-1 (0 if not cheaper)."""
    if not group_prices or len(group_prices) < 2 or not price:
        return 0.0
    med = statistics.median(group_prices)
    if med <= 0:
        return 0.0
    return max(0.0, min(1.0, (med - price) / med))


def minmax(values: List[float]) -> List[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def value_score(quality: Optional[float], price_efficiency: Optional[float],
                cross_site_gap: float, weights=WEIGHTS) -> float:
    """Weighted 0-100 score. ``quality`` may be a real or an estimated quality;
    None contributes 0."""
    wq, wp, wg = weights
    q = quality or 0.0
    pe = price_efficiency or 0.0
    gap = cross_site_gap or 0.0
    return round(100 * (wq * q + wp * pe + wg * gap), 2)


def compute_scores(wines, weights=WEIGHTS):
    """Set quality, quality_est, price_efficiency, cross_site_gap and value_score."""
    for w in wines:
        w.quality = quality_from_inputs(w.vivino_rating, best_critic_score(w.critic_scores))
    priors = unrated_priors(wines)

    q_eff, pe_raw = [], []
    for w in wines:
        if w.quality is not None:
            w.quality_est = None
            q = w.quality
        else:
            w.quality_est = priors.get(w.wine_type, priors.get(None))
            q = w.quality_est
        q_eff.append(q)
        p750 = price_per_750(w.price_thb, w.size_ml)
        pe_raw.append((q / p750) if (q is not None and p750) else None)

    # normalize price efficiency on a log scale (raw quality/baht is heavily skewed)
    idx = [i for i, v in enumerate(pe_raw) if v is not None and v > 0]
    norm = minmax([math.log(pe_raw[i]) for i in idx])
    pe_map = dict(zip(idx, norm))

    # compare like with like: a half bottle isn't "50% cheaper" than a full one
    groups = {}
    for w in wines:
        p750 = price_per_750(w.price_thb, w.size_ml)
        if w.match_group is not None and p750:
            groups.setdefault(w.match_group, []).append(p750)

    for i, w in enumerate(wines):
        w.price_efficiency = pe_map.get(i, 0.0)
        gp = groups.get(w.match_group)
        p750 = price_per_750(w.price_thb, w.size_ml)
        w.cross_site_gap = cross_site_gap(p750, gp) if (gp and p750) else 0.0
        w.value_score = value_score(q_eff[i], w.price_efficiency, w.cross_site_gap, weights)
    return wines
