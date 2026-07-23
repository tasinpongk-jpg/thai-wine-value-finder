"""Build the read-only Cloudflare catalog from the checked-in SQLite snapshot."""
from __future__ import annotations

import json
from pathlib import Path

import store
from sources import SOURCES


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "public" / "data" / "wines.json"


def main() -> None:
    wines = store.read_wines(store.DEFAULT_DB)
    for wine in wines:
        wine["site"] = SOURCES.get(wine["source"], {}).get("label", wine["source"])

    latest = max((wine.get("scraped_at") or "" for wine in wines), default="")
    payload = {
        "latest_scrape": latest,
        "sources": len({wine["source"] for wine in wines}),
        "wines": wines,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Built {len(wines):,} wines -> {OUTPUT}")


if __name__ == "__main__":
    main()
