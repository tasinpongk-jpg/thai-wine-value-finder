"""Build the read-only Cloudflare catalog from the checked-in SQLite snapshot."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import store
from sources import SOURCES


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "public" / "data" / "wines.json"
BANGKOK = ZoneInfo("Asia/Bangkok")


def _bangkok_day(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BANGKOK)
    return parsed.astimezone(BANGKOK).date().isoformat()


def main() -> None:
    wines = store.read_wines(store.DEFAULT_DB)
    for wine in wines:
        wine["site"] = SOURCES.get(wine["source"], {}).get("label", wine["source"])

    per_source = {}
    for wine in wines:
        source = wine["source"]
        entry = per_source.setdefault(
            source,
            {
                "source": source,
                "site": wine["site"],
                "listings": 0,
                "updated_at": "",
            },
        )
        entry["listings"] += 1
        entry["updated_at"] = max(
            entry["updated_at"],
            wine.get("scraped_at") or "",
        )

    latest = max(
        (entry["updated_at"] for entry in per_source.values()),
        default="",
    )
    latest_day = _bangkok_day(latest)
    source_freshness = sorted(per_source.values(), key=lambda item: item["site"])
    for entry in source_freshness:
        entry["updated_day"] = _bangkok_day(entry["updated_at"])
    fresh_sources = sum(
        entry["updated_day"] == latest_day
        for entry in source_freshness
    )
    payload = {
        "latest_scrape": latest,
        "latest_scrape_day": latest_day,
        "sources": len(per_source),
        "fresh_sources": fresh_sources,
        "source_freshness": source_freshness,
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
