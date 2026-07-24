"""Refresh the public catalog while retaining the last good data for failed shops.

This is the entry point used by the scheduled GitHub Actions workflow. Each shop
is fetched independently. A failed or suspiciously small response keeps that
shop's previous snapshot, while successful shops are updated atomically.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
import time
from collections import Counter
from dataclasses import fields
from multiprocessing import get_context

from enrich.match import assign_match_groups
from enrich.value import compute_scores
from models import Wine
from scrape import SCRAPERS
from scrapers.base import PoliteSession
import store


MIN_RETAIN_RATIO = 0.5
WINE_FIELDS = {field.name for field in fields(Wine)}


def _as_wine(row: dict) -> Wine:
    return Wine(**{key: row.get(key) for key in WINE_FIELDS})


def _scrape_source(key, module, use_cache, timeout, retries):
    started = time.monotonic()
    session = PoliteSession(
        use_cache=use_cache,
        timeout=timeout,
        retries=retries,
    )
    wines = module.scrape(session)
    return key, wines, time.monotonic() - started


def _scrape_worker(connection, key, use_cache, timeout, retries):
    """Run one scraper in an isolated process so its total time is bounded."""
    try:
        _, wines, elapsed = _scrape_source(
            key,
            SCRAPERS[key],
            use_cache,
            timeout,
            retries,
        )
        connection.send(("ok", wines, elapsed))
    except Exception as exc:
        connection.send(("error", f"{type(exc).__name__}: {exc}", 0))
    finally:
        connection.close()


def collect_sources(
    *,
    use_cache=False,
    timeout=20,
    retries=2,
    source_timeout=120,
    scrapers=SCRAPERS,
):
    """Return successful source snapshots and a reason for every fallback."""
    fresh = {}
    failures = {}
    if scrapers is not SCRAPERS:
        for key, module in scrapers.items():
            try:
                _, wines, elapsed = _scrape_source(
                    key,
                    module,
                    use_cache,
                    timeout,
                    retries,
                )
                fresh[key] = wines
                print(f"{key:14} fetched {len(wines):5} wines in {elapsed:.1f}s")
            except Exception as exc:
                failures[key] = f"{type(exc).__name__}: {exc}"
                print(f"{key:14} fallback — {failures[key]}")
        return fresh, failures

    context = get_context("spawn")
    pending = {}
    for key in scrapers:
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=_scrape_worker,
            args=(sender, key, use_cache, timeout, retries),
        )
        process.start()
        sender.close()
        pending[key] = (process, receiver, time.monotonic())

    while pending:
        for key, (process, receiver, started) in list(pending.items()):
            if receiver.poll():
                status, payload, elapsed = receiver.recv()
                if status == "ok":
                    fresh[key] = payload
                    print(
                        f"{key:14} fetched {len(payload):5} wines "
                        f"in {elapsed:.1f}s",
                        flush=True,
                    )
                else:
                    failures[key] = payload
                    print(f"{key:14} fallback — {payload}", flush=True)
                process.join(timeout=5)
                receiver.close()
                del pending[key]
                continue
            if not process.is_alive():
                failures[key] = f"worker exited with code {process.exitcode}"
                print(f"{key:14} fallback — {failures[key]}", flush=True)
                process.join()
                receiver.close()
                del pending[key]
                continue
            if time.monotonic() - started >= source_timeout:
                failures[key] = f"source exceeded {source_timeout}s total timeout"
                print(f"{key:14} fallback — {failures[key]}", flush=True)
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join()
                receiver.close()
                del pending[key]
        time.sleep(0.2)
    return fresh, failures


def validate_sources(fresh, existing_rows, failures, min_retain_ratio=MIN_RETAIN_RATIO):
    """Reject empty, malformed, or unexpectedly small source snapshots."""
    previous_counts = Counter(row["source"] for row in existing_rows)
    accepted = {}
    for key, wines in fresh.items():
        valid = [
            wine
            for wine in wines
            if wine.source == key
            and wine.source_id
            and wine.name
            and wine.price_thb is not None
            and wine.price_thb > 0
        ]
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


def _stage_catalog(wines, updated_sources, db_path):
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


def refresh_catalog(
    db_path=store.DEFAULT_DB,
    *,
    use_cache=False,
    timeout=20,
    retries=2,
    source_timeout=120,
    scrapers=SCRAPERS,
):
    existing_rows = store.read_wines(db_path)
    fresh, failures = collect_sources(
        use_cache=use_cache,
        timeout=timeout,
        retries=retries,
        source_timeout=source_timeout,
        scrapers=scrapers,
    )
    accepted = validate_sources(fresh, existing_rows, failures)
    if not accepted:
        raise RuntimeError("all shop refreshes failed; catalog was not changed")

    wines = merge_catalog(existing_rows, accepted)
    print(f"Recomputing matches and value scores for {len(wines):,} listings...")
    assign_match_groups(wines)
    compute_scores(wines)
    _stage_catalog(wines, set(accepted), db_path)

    print(f"Updated {len(accepted)}/{len(scrapers)} shops -> {db_path}")
    for key in sorted(failures):
        print(f"Retained last-good {key}: {failures[key]}")
    return {
        "updated_sources": sorted(accepted),
        "retained_sources": sorted(failures),
        "listings": len(wines),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Safely refresh the public wine catalog.",
    )
    parser.add_argument("--db", default=store.DEFAULT_DB)
    parser.add_argument(
        "--cache",
        action="store_true",
        help="allow the one-day HTTP cache instead of forcing live requests",
    )
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--source-timeout",
        type=int,
        default=120,
        help="maximum wall time per shop in seconds",
    )
    args = parser.parse_args(argv)
    refresh_catalog(
        args.db,
        use_cache=args.cache,
        timeout=args.timeout,
        retries=args.retries,
        source_timeout=args.source_timeout,
    )


if __name__ == "__main__":
    main()
