"""Compute the 0-100 value score and its three visible components."""
from __future__ import annotations

import math
import statistics
from typing import List, Optional

from enrich.critic_scores import best_critic_score

WEIGHTS = (0.45, 0.35, 0.20)  # quality, price_efficiency, cross_site_gap
STANDARD_ML = 750
_MIN_ML, _MAX_ML = 50, 27000


def price_per_750(price: Optional[float], size_ml: Optional[int]) -> Optional[float]:
    """Price normalized to a standard 750 ml bottle (unchanged if size unknown)."""
    if not price or price <= 0:
        return None
    if size_ml and _MIN_ML <= size_ml <= _MAX_ML:
        return price * STANDARD_ML / size_ml
    return price


def quality_from_inputs(vivino_rating: Optional[float],
                        critic_best: Optional[int]) -> Optional[float]:
    """Normalize the best available rating to 0-1. Vivino (0-5) wins over critic pts."""
    if vivino_rating is not None:
        return max(0.0, min(1.0, vivino_rating / 5.0))
    if critic_best is not None:
        return max(0.0, min(1.0, (critic_best - 80) / 20.0))
    return None


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
    wq, wp, wg = weights
    pe = price_efficiency or 0.0
    gap = cross_site_gap or 0.0
    if quality is None:
        total = wp * pe + wg * gap            # unrated wines naturally rank lower
    else:
        total = wq * quality + wp * pe + wg * gap
    return round(100 * total, 2)


def compute_scores(wines, weights=WEIGHTS):
    """Set quality, price_efficiency, cross_site_gap and value_score on each Wine."""
    pe_raw = []
    for w in wines:
        critic_best = best_critic_score(w.critic_scores)
        w.quality = quality_from_inputs(w.vivino_rating, critic_best)
        p750 = price_per_750(w.price_thb, w.size_ml)
        pe_raw.append((w.quality / p750) if (w.quality and p750) else None)

    # normalize price efficiency on a log scale (raw quality/baht is heavily skewed)
    idx = [i for i, v in enumerate(pe_raw) if v and v > 0]
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
        w.value_score = value_score(w.quality, w.price_efficiency, w.cross_site_gap, weights)
    return wines
