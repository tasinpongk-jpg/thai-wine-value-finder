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

from scrapers.base import PoliteSession
from scrapers import (winedutyfree, wineplus, spirithouse, wishbeer,
                      winestoreasia)
from enrich import vivino
from enrich.match import assign_match_groups
from enrich.value import compute_scores
import store

SCRAPERS = {
    "winedutyfree": winedutyfree,
    "wishbeer": wishbeer,
    "winestoreasia": winestoreasia,
    "wineplus": wineplus,
    "spirithouse": spirithouse,
}


def run(sites=None, use_cache=True, vivino_limit=0, db_path=store.DEFAULT_DB):
    sites = sites or list(SCRAPERS)
    session = PoliteSession(use_cache=use_cache)
    all_wines = []

    print("Scraping sites...")
    for key in sites:
        mod = SCRAPERS[key]
        t0 = time.time()
        try:
            wines = mod.scrape(session)
            all_wines.extend(wines)
            print(f"  {key:14} {len(wines):5} wines   ({time.time() - t0:.1f}s)")
        except Exception as e:  # one site failing must not kill the run
            print(f"  {key:14} FAILED: {type(e).__name__}: {e}")

    if not all_wines:
        print("No wines scraped — nothing to save.")
        return []

    print(f"\nTotal scraped: {len(all_wines)} wines")

    if vivino_limit:
        print(f"Vivino lookup (best-effort, up to {vivino_limit})...")
        vivino.enrich_wines(all_wines, session=session, limit=vivino_limit)

    print("Matching across sites...")
    assign_match_groups(all_wines)
    groups = len({w.match_group for w in all_wines})
    multi = sum(1 for w in all_wines if w.match_group is not None
                and sum(1 for x in all_wines if x.match_group == w.match_group) > 1)
    print(f"  {groups} distinct wines; {multi} listings have a cross-site match")

    print("Scoring...")
    compute_scores(all_wines)

    store.save(all_wines, db_path)
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
        print(f"   {w.value_score:5.1f} | q={q} | {w.price_thb:>7.0f}฿ | "
              f"{w.source:12} | {w.name[:46]}")


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
