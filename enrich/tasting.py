"""Pull tasting sections (appearance / nose / palate / pairing / body) out of the
loosely-structured prose that some shops put in their product descriptions."""
from __future__ import annotations

import re

_LABEL_RE = re.compile(r"([A-Za-z][A-Za-z /]{2,25}?)\s*:\s*")

# label (lowercased) -> canonical field
_CANON = {
    "appearance": "appearance", "colour": "appearance", "color": "appearance",
    "aroma": "nose", "aromas": "nose", "nose": "nose", "bouquet": "nose",
    "palate": "palate", "taste": "palate", "on the palate": "palate", "mouth": "palate",
    "finish": "finish",
    "pairing": "pairing", "food pairing": "pairing", "serve with": "pairing",
    "style": "body", "body": "body",
}


def parse_sections(text) -> dict:
    if not text:
        return {}
    text = str(text)
    matches = list(_LABEL_RE.finditer(text))
    out = {}
    for i, m in enumerate(matches):
        canon = _CANON.get(m.group(1).strip().lower())
        if not canon or canon in out:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip(" .;,-•")
        if value:
            out[canon] = value
    return out
