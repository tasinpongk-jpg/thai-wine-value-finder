"""Extract wine critic scores embedded in free-form product text.

Returns a list of ``{"critic": <code>, "score": <int 80-100>}``. Coverage across
the Thai sites is sparse, so this is one input to quality, not the only one.
"""
from __future__ import annotations

import re
from typing import List, Dict, Optional

_FLOOR, _CEIL = 80, 100

# canonical critic code -> regex matching its code or full name
_CRITIC_SRC = [
    (r"\bJS\b|James\s+Suckling", "JS"),
    (r"\bWS\b|Wine\s+Spectator", "WS"),
    (r"\bRP\b|Robert\s+Parker", "RP"),
    (r"\bWA\b|Wine\s+Advocate", "WA"),
    (r"\bWE\b|Wine\s+Enthusiast", "WE"),
    (r"\bJD\b|Jeb\s+Dunnuck", "JD"),
    (r"\bDecanter\b|\bDEC\b", "DEC"),
    (r"\bVinous\b|\bVN\b", "VN"),
]
_SCORE = r"(\d{2,3})(?:\s*-\s*(\d{2,3}))?"
_NAMED = [(re.compile(r"(?:" + src + r")\s*[:\-]?\s*" + _SCORE, re.I), code)
          for src, code in _CRITIC_SRC]
_POINTS = re.compile(r"\b(\d{2,3})\s*(?:points|pts|/\s*100|\+)", re.I)


def _in_range(n: int) -> bool:
    return _FLOOR <= n <= _CEIL


def extract_critic_scores(text) -> List[Dict]:
    if not text:
        return []
    s = str(text)
    found: List[Dict] = []
    seen = set()
    consumed = []  # spans of numbers already attributed to a named critic

    for rx, code in _NAMED:
        for m in rx.finditer(s):
            upper = m.group(2) or m.group(1)
            score = int(upper)
            num_start = m.start(1)
            num_end = m.end(2) if m.group(2) else m.end(1)
            consumed.append((num_start, num_end))
            if _in_range(score) and (code, score) not in seen:
                seen.add((code, score))
                found.append({"critic": code, "score": score})

    for m in _POINTS.finditer(s):
        span = m.span(1)
        if any(a <= span[0] < b for a, b in consumed):
            continue
        score = int(m.group(1))
        if _in_range(score) and ("points", score) not in seen:
            seen.add(("points", score))
            found.append({"critic": "points", "score": score})

    return found


def best_critic_score(scores: List[Dict]) -> Optional[int]:
    vals = [d["score"] for d in (scores or []) if "score" in d]
    return max(vals) if vals else None
