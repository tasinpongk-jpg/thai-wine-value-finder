"""Pure helpers that turn messy site data into the canonical Wine fields."""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Optional

from sources import WINE_TYPE_CATEGORY_HINTS

_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|cl|l)\b", re.IGNORECASE)
_VINTAGE_RE = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")
_UNIT_TO_ML = {"ml": 1, "cl": 10, "l": 1000}

# colour words for sites that only put the type in free text (winedutyfree = Thai)
_TEXT_TYPE_HINTS = [
    ("ไวน์แดง", "Red"), ("red wine", "Red"), ("red", "Red"),
    ("ไวน์ขาว", "White"), ("white wine", "White"), ("white", "White"),
    ("โรเซ่", "Rosé"), ("rosé", "Rosé"), ("rose", "Rosé"),
    ("แชมเปญ", "Champagne"), ("champagne", "Champagne"),
    ("สปาร์กลิง", "Sparkling"), ("sparkling", "Sparkling"),
]


def clean_text(s) -> str:
    """Decode HTML entities (&#8217; -> ’) and trim — for display names."""
    if not s:
        return ""
    return html.unescape(str(s)).strip()


def short_desc(text, limit: int = 320) -> Optional[str]:
    """Collapse whitespace and trim a blurb to ~limit chars on a word boundary."""
    if not text:
        return None
    s = re.sub(r"\s+", " ", html.unescape(str(text))).strip()
    if not s:
        return None
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" .,;:-") + "…"


def parse_wc_price(price_str, minor_unit: int) -> Optional[float]:
    """WooCommerce / Store API price: integer in minor units (satang)."""
    if price_str is None or price_str == "":
        return None
    try:
        return int(str(price_str)) / (10 ** int(minor_unit))
    except (ValueError, TypeError):
        return None


def parse_price_text(text) -> Optional[float]:
    """Pull a baht amount out of a free-form price string."""
    if text is None:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(text))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_size_ml(text) -> Optional[int]:
    if not text:
        return None
    m = _SIZE_RE.search(str(text))
    if not m:
        return None
    value = float(m.group(1)) * _UNIT_TO_ML[m.group(2).lower()]
    return int(round(value))


def parse_vintage(text) -> Optional[int]:
    if not text:
        return None
    s = str(text)
    if re.search(r"\bnv\b", s, re.IGNORECASE):
        return None
    # strip size tokens so e.g. "2000ml" can't masquerade as a year
    s = _SIZE_RE.sub(" ", s)
    m = _VINTAGE_RE.search(s)
    return int(m.group(1)) if m else None


def canonical_wine_type(categories, text: str = "") -> str:
    """Map a list of category names (and optional free text) to a canonical type."""
    for cat in categories or []:
        hint = WINE_TYPE_CATEGORY_HINTS.get(str(cat).strip().lower())
        if hint:
            return hint
    low = (text or "").lower()
    for needle, canonical in _TEXT_TYPE_HINTS:
        if needle in low:
            return canonical
    return "Other"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    """Lowercase, accent-fold, drop size/vintage/punctuation -> matching key."""
    if not name:
        return ""
    s = _strip_accents(str(name)).lower()
    s = _SIZE_RE.sub(" ", s)
    s = _VINTAGE_RE.sub(" ", s)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()
