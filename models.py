"""Normalized data model shared across scrapers, enrichment and storage."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


WINE_TYPES = {"Red", "White", "Rosé", "Sparkling", "Champagne",
              "Dessert", "Fortified", "Orange", "Other"}


@dataclass
class Wine:
    # identity
    source: str                       # site key, e.g. "wishbeer"
    source_id: str                    # stable id within that site
    name: str                         # cleaned product name
    # core attributes
    price_thb: Optional[float] = None
    vintage: Optional[int] = None     # year, or None for NV / unknown
    wine_type: str = "Other"          # canonical WINE_TYPES
    size_ml: Optional[int] = None
    country: Optional[str] = None
    region: Optional[str] = None
    grape: Optional[str] = None
    url: Optional[str] = None
    image: Optional[str] = None
    # descriptive / tasting (for the detail view)
    producer: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None        # e.g. "Full-Bodied"
    alcohol: Optional[str] = None     # e.g. "14.5%"
    nose: Optional[str] = None        # aroma
    palate: Optional[str] = None
    appearance: Optional[str] = None
    pairing: Optional[str] = None
    # ratings (raw inputs to scoring)
    critic_scores: list = field(default_factory=list)   # [{"critic": "JS", "score": 95}]
    vivino_rating: Optional[float] = None               # 0-5 stars
    vivino_count: Optional[int] = None                  # number of ratings
    vivino_source: Optional[str] = None                 # "site" | "lookup" | None
    review_rating: Optional[float] = None               # store review stars 0-5
    review_count: Optional[int] = None
    # computed by enrichment
    quality: Optional[float] = None         # 0-1
    price_efficiency: Optional[float] = None  # 0-1
    cross_site_gap: Optional[float] = None    # 0-1
    value_score: Optional[float] = None       # 0-100
    match_group: Optional[int] = None
    match_low_confidence: bool = False
    scraped_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
