"""Refresh the public catalog while retaining the last good data for failed shops.

This is the entry point used by the scheduled GitHub Actions workflow. Each shop
is fetched independently. A failed or suspiciously small response keeps that
shop's previous snapshot, while successful shops are updated atomically.
"""
from __future__ import annotations

import argparse
import time
from multiprocessing import get_context

from catalog import (
    MIN_PRICE_PER_750_THB,
    MIN_RETAIN_RATIO,
    _as_wine,
    merge_catalog,
    rebuild_catalog,
    stage_catalog,
    validate_sources,
)
from scrape import SCRAPERS
from scrapers.base import PoliteSession
import store

_stage_catalog = stage_catalog  # backwards-compatible name

# validate/merge/stage now live in catalog.py (shared with scrape.py); keep the
# old names importable from here.
__all__ = [
    "MIN_PRICE_PER_750_THB", "MIN_RETAIN_RATIO", "_as_wine", "_stage_catalog",
    "collect_sources", "merge_catalog", "rebuild_catalog", "refresh_catalog",
    "stage_catalog", "validate_sources",
]


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


def refresh_catalog(
    db_path=store.DEFAULT_DB,
    *,
    use_cache=False,
    timeout=20,
    retries=2,
    source_timeout=120,
    scrapers=SCRAPERS,
):
    fresh, failures = collect_sources(
        use_cache=use_cache,
        timeout=timeout,
        retries=retries,
        source_timeout=source_timeout,
        scrapers=scrapers,
    )
    wines, accepted, retired = rebuild_catalog(db_path, fresh, failures, scrapers)
    if not accepted:
        raise RuntimeError("all shop refreshes failed; catalog was not changed")

    print(f"Updated {len(accepted)}/{len(scrapers)} shops -> {db_path}")
    for key in sorted(retired):
        print(f"Dropped retired source {key}")
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
