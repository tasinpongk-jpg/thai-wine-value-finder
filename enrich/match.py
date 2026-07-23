"""Group the same wine across sites via fuzzy name + vintage + size matching.

Greedy single-pass clustering against each cluster's first member. Low-confidence
joins (matched only after ignoring word order / extra words) are flagged, not hidden.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from enrich.normalize import normalize_name

DEFAULT_THRESHOLD = 90


def _compatible(a, b) -> bool:
    """Same product requires matching vintage and size when both are known."""
    if a.vintage is not None and b.vintage is not None and a.vintage != b.vintage:
        return False
    if a.size_ml is not None and b.size_ml is not None and a.size_ml != b.size_ml:
        return False
    return True


def assign_match_groups(wines, threshold: int = DEFAULT_THRESHOLD):
    norms = [normalize_name(w.name) for w in wines]
    clusters = []  # each: {"rep": norm, "repw": Wine, "members": [idx, ...]}

    for i, w in enumerate(wines):
        placed = False
        for c in clusters:
            # must be compatible with EVERY member, so a no-vintage listing can't
            # bridge two distinct vintages (or sizes) into one group
            if any(not _compatible(w, wines[m]) for m in c["members"]):
                continue
            if not norms[i] or not c["rep"]:
                continue
            if fuzz.token_set_ratio(norms[i], c["rep"]) >= threshold:
                if fuzz.token_sort_ratio(norms[i], c["rep"]) < threshold:
                    w.match_low_confidence = True
                c["members"].append(i)
                placed = True
                break
        if not placed:
            clusters.append({"rep": norms[i], "repw": w, "members": [i]})

    for gid, c in enumerate(clusters):
        multi = len(c["members"]) > 1
        for idx in c["members"]:
            wines[idx].match_group = gid
            if not multi:
                wines[idx].match_low_confidence = False  # singletons are certain
    return wines
