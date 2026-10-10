"""Shared catalog pipeline: validate fresh shop snapshots, merge them with the
last-good rows of every other shop, rescore the whole catalog, and atomically
replace the SQLite snapshot.

Used by both ``daily_refresh.py`` (scheduled) and ``scrape.py`` (manual), so a
partial run (``scrape.py --sites X``) can never leave stale rows or match-group
ids that collide with another shop's.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from collections import Counter
from dataclasses import fields

from enrich.match import assign_match_groups
from enrich.value import compute_scores, price_per_750
from models import Wine
import store

MIN_RETAIN_RATIO = 0.5
# Cheapest real 750 ml wine on these shops is ~฿230+; anything under this is a
# wrong currency (e.g. Wine Store Asia's SGD-priced SKUs) or a placeholder.
MIN_PRICE_PER_750_THB = 150
WINE_FIELDS = {field.name for field in fields(Wine)}


def _as_wine(row: dict) -> Wine:
    return Wine(**{key: row.get(key) for key in WINE_FIELDS})


def validate_sources(fresh, existing_rows, failures, min_retain_ratio=MIN_RETAIN_RATIO,
                     min_price_per_750=MIN_PRICE_PER_750_THB):
    """Reject empty, malformed, implausibly priced, or unexpectedly small snapshots.

    Individual listings priced below ``min_price_per_750`` THB per 750 ml are
    dropped (no real wine sells that cheap in Thailand; such prices are almost
    always a wrong currency or a placeholder). The shop is then rejected as a
    whole if what's left is suspiciously small versus its previous snapshot.
    """
    previous_counts = Counter(row["source"] for row in existing_rows)
    accepted = {}
    for key, wines in fresh.items():
        valid, implausible = [], 0
        for wine in wines:
            if not (wine.source == key and wine.source_id and wine.name
                    and wine.price_thb is not None and wine.price_thb > 0):
                continue
            p750 = price_per_750(wine.price_thb, wine.size_ml)
            if p750 is None or p750 < min_price_per_750:
                implausible += 1
                continue
            valid.append(wine)
        if implausible:
            print(f"{key:14} dropped {implausible} listings priced below "
                  f"฿{min_price_per_750:,.0f} per 750 ml")
        previous = previous_counts.get(key, 0)
        minimum = max(1, int(previous * min_retain_ratio)) if previous else 1
        if len(valid) < minimum:
            failures[key] = (
                f"suspicious result: {len(valid)} valid wines, "
                f"minimum {minimum} from previous {previous}"
            )
            print(f"{key:14} fallback — {failures[key]}")
            continue
        accepted[key] = valid
    return accepted


def merge_catalog(existing_rows, accepted):
    """Use fresh rows for accepted shops and last-good rows for every other shop."""
    updated_sources = set(accepted)
    merged = [
        _as_wine(row)
        for row in existing_rows
        if row["source"] not in updated_sources
    ]
    for key in sorted(accepted):
        merged.extend(accepted[key])
    return merged


def stage_catalog(wines, updated_sources, db_path):
    """Write a validated database copy, then atomically replace the live snapshot."""
    db_path = os.path.abspath(db_path)
    parent = os.path.dirname(db_path)
    os.makedirs(parent, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".wine-refresh-", dir=parent) as tmp:
        staged = os.path.join(tmp, "wine.db")
        if os.path.exists(db_path):
            shutil.copy2(db_path, staged)
        conn = store.connect(staged)
        try:
            store.init_db(conn)
            conn.executemany(
                "DELETE FROM wines WHERE source=?",
                [(source,) for source in updated_sources],
            )
            conn.commit()
        finally:
            conn.close()

        store.save(wines, staged)
        check = sqlite3.connect(staged)
        try:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
            count = check.execute("SELECT COUNT(*) FROM wines").fetchone()[0]
        finally:
            check.close()
        if integrity != "ok" or count != len(wines):
            raise RuntimeError(
                f"staged database validation failed: integrity={integrity}, "
                f"rows={count}, expected={len(wines)}"
            )
        os.replace(staged, db_path)


def rebuild_catalog(db_path, fresh, failures, active_sources):
    """Validate ``fresh`` snapshots, merge with last-good rows, rescore, and save.

    ``active_sources`` are the shop keys that still exist; rows from any other
    source in the database are purged. Returns ``(wines, accepted, retired)``.
    ``wines`` is empty (and the database untouched) when nothing was accepted.
    """
    all_rows = store.read_wines(db_path)
    retired = {row["source"] for row in all_rows} - set(active_sources)
    existing_rows = [row for row in all_rows if row["source"] not in retired]
    accepted = validate_sources(fresh, existing_rows, failures)
    if not accepted:
        return [], accepted, retired
    wines = merge_catalog(existing_rows, accepted)
    print(f"Recomputing matches and value scores for {len(wines):,} listings...")
    assign_match_groups(wines)
    compute_scores(wines)
    stage_catalog(wines, set(accepted) | retired, db_path)
    return wines, accepted, retired
