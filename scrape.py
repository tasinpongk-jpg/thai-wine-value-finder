"""Gather + enrich + score all wines, then save to the SQLite database.

    python scrape.py                 # scrape everything (uses 1-day cache)
    python scrape.py --no-cache      # force fresh fetches
    python scrape.py --vivino 200    # also try up to 200 Vivino lookups
    python scrape.py --sites wishbeer spirithouse

Then view it with:  streamlit run dashboard.py
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

from scrapers.base import PoliteSession
from scrapers import winedutyfree, spirithouse, wishbeer, winestoreasia
from enrich import vivino
import catalog
import store

SCRAPERS = {
    "winedutyfree": winedutyfree,
    "wishbeer": wishbeer,
    "winestoreasia": winestoreasia,
    "spirithouse": spirithouse,
}


def run(sites=None, use_cache=True, vivino_limit=0, db_path=store.DEFAULT_DB,
        scrapers=None):
    """Scrape ``sites`` (default: all) and fold them into the catalog at ``db_path``.

    Uses the same validate/merge/stage path as ``daily_refresh``: the scraped
    shops' old rows are replaced (so delisted wines disappear), other shops keep
    their last-good rows, and match groups + scores are recomputed over the
    whole catalog so group ids stay consistent across shops.
    """
    scrapers = scrapers or SCRAPERS
    sites = sites or list(scrapers)
    session = PoliteSession(use_cache=use_cache)
    fresh, failures = {}, {}

    print("Scraping sites...")
    for key in sites:
        mod = scrapers[key]
        t0 = time.time()
        try:
            wines = mod.scrape(session)
            fresh[key] = wines
            print(f"  {key:14} {len(wines):5} wines   ({time.time() - t0:.1f}s)")
        except Exception as e:  # one site failing must not kill the run
            failures[key] = f"{type(e).__name__}: {e}"
            print(f"  {key:14} FAILED: {failures[key]}")

    scraped = [w for wines in fresh.values() for w in wines]
    if not scraped:
        print("No wines scraped — nothing to save.")
        return []

    print(f"\nTotal scraped: {len(scraped)} wines")

    if vivino_limit:
        print(f"Vivino lookup (best-effort, up to {vivino_limit})...")
        vivino.enrich_wines(scraped, session=session, limit=vivino_limit)

    all_wines, accepted, _ = catalog.rebuild_catalog(db_path, fresh, failures, scrapers)
    if not accepted:
        print("Every scraped shop failed validation — catalog left unchanged.")
        return []
    for key in sorted(failures):
        print(f"  kept last-good {key}: {failures[key]}")

    sizes = Counter(w.match_group for w in all_wines if w.match_group is not None)
    multi = sum(n for n in sizes.values() if n > 1)
    print(f"  {len(sizes)} distinct wines; {multi} listings have a cross-site match")

    _summary(all_wines, db_path)
    return all_wines


def _summary(wines, db_path):
    rated = [w for w in wines if w.quality is not None]
    print(f"\nSaved {len(wines)} wines -> {db_path}")
    print(f"  with a quality rating: {len(rated)} "
          f"({100 * len(rated) // max(1, len(wines))}%)")
    print("  Top 10 by value score:")
    for w in sorted(wines, key=lambda x: x.value_score or 0, reverse=True)[:10]:
        q = f"{w.quality:.2f}" if w.quality is not None else "  - "
        score = f"{w.value_score:5.1f}" if w.value_score is not None else "  -  "
        price = f"{w.price_thb:>7.0f}" if w.price_thb is not None else "      -"
        print(f"   {score} | q={q} | {price}฿ | "
              f"{w.source:12} | {(w.name or '')[:46]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Scrape + score Thai wine catalogs.")
    ap.add_argument("--sites", nargs="+", choices=list(SCRAPERS), default=None)
    ap.add_argument("--no-cache", action="store_true", help="force fresh fetches")
    ap.add_argument("--vivino", type=int, default=0, metavar="N",
                    help="best-effort Vivino lookups for unrated wines (default 0)")
    ap.add_argument("--db", default=store.DEFAULT_DB)
    args = ap.parse_args(argv)
    run(sites=args.sites, use_cache=not args.no_cache,
        vivino_limit=args.vivino, db_path=args.db)


if __name__ == "__main__":
    sys.exit(main())
