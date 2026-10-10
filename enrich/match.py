"""Group the same wine across sites via fuzzy name + vintage + size matching.

Greedy single-pass clustering against each cluster's first member. Low-confidence
joins (matched only after ignoring word order / extra words) are flagged, not hidden.

Performance: all name-vs-name ``token_set_ratio`` scores are computed up front in
one vectorized, multi-threaded ``rapidfuzz.process.cdist`` call (float64, so the
threshold comparison is bit-for-bit the same as calling ``fuzz.token_set_ratio``
pair by pair), candidate clusters are found with one numpy mask per listing, and
each cluster keeps the set of vintages/sizes of its members so
the "compatible with every member" check is O(1). The greedy order and therefore
the resulting groups are unchanged.
"""
from __future__ import annotations

import numpy as np
from rapidfuzz import fuzz, process

from enrich.normalize import normalize_name

DEFAULT_THRESHOLD = 90
# compute the score matrix in row blocks so memory stays bounded (block x n float64)
_BLOCK_ROWS = 512


def _compatible(a, b) -> bool:
    """Same product requires matching vintage and size when both are known."""
    if a.vintage is not None and b.vintage is not None and a.vintage != b.vintage:
        return False
    if a.size_ml is not None and b.size_ml is not None and a.size_ml != b.size_ml:
        return False
    return True


def _fits(values: set, value) -> bool:
    """A listing is compatible with every member iff its (known) value equals all
    of the members' known values. Unknown on either side is compatible."""
    return value is None or not values or values == {value}


class _Cluster:
    __slots__ = ("rep", "members", "vintages", "sizes")

    def __init__(self, rep: int, wine):
        self.rep = rep            # index of the first member (its name is the rep)
        self.members = [rep]
        self.vintages = {wine.vintage} - {None}
        self.sizes = {wine.size_ml} - {None}

    def accepts(self, wine) -> bool:
        return _fits(self.vintages, wine.vintage) and _fits(self.sizes, wine.size_ml)

    def add(self, idx: int, wine):
        self.members.append(idx)
        if wine.vintage is not None:
            self.vintages.add(wine.vintage)
        if wine.size_ml is not None:
            self.sizes.add(wine.size_ml)


def assign_match_groups(wines, threshold: int = DEFAULT_THRESHOLD):
    norms = [normalize_name(w.name) for w in wines]
    n = len(wines)
    clusters: list[_Cluster] = []
    # rep index of each cluster, in creation order (clusters with an empty rep name
    # can never match, so they get -1 and are masked out)
    reps = np.full(n, -1, dtype=np.int64)

    for start in range(0, n, _BLOCK_ROWS):
        stop = min(n, start + _BLOCK_ROWS)
        # wine i is only ever compared with reps that come before it (< stop)
        scores = process.cdist(norms[start:stop], norms[:stop], scorer=fuzz.token_set_ratio,
                               dtype=np.float64, score_cutoff=threshold, workers=-1)
        for i in range(start, stop):
            w = wines[i]
            placed = False
            if norms[i] and clusters:
                k = len(clusters)
                row = scores[i - start]
                live = reps[:k]
                hits = np.flatnonzero((live >= 0) & (row[np.maximum(live, 0)] >= threshold))
                for ci in hits:           # in cluster-creation order, like before
                    c = clusters[ci]
                    if not c.accepts(w):
                        continue
                    if fuzz.token_sort_ratio(norms[i], norms[c.rep]) < threshold:
                        w.match_low_confidence = True
                    c.add(i, w)
                    placed = True
                    break
            if not placed:
                reps[len(clusters)] = i if norms[i] else -1
                clusters.append(_Cluster(i, w))

    for gid, c in enumerate(clusters):
        multi = len(c.members) > 1
        for idx in c.members:
            wines[idx].match_group = gid
            if not multi:
                wines[idx].match_low_confidence = False  # singletons are certain
    return wines
