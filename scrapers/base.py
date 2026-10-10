"""Polite, cached HTTP layer shared by all scrapers.

- identifies itself with a descriptive User-Agent
- rate-limits between requests
- caches every response to disk (default 1 day) so re-runs don't re-hit the sites
- retries only transient failures (connection errors, timeouts, 5xx, 429) with
  exponential backoff, honouring Retry-After; 4xx and bad JSON fail immediately
- writes cache files atomically
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import time
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

from sources import USER_AGENT

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")


def _install_dns_pins():
    """Opt-in host->IP pinning for networks with flaky DNS.

    Set WINEVALUE_PIN_HOSTS="host=ip,host=ip". The real hostname is still used for
    SNI/Host headers, so TLS stays valid. Off by default; harmless in normal use.
    """
    raw = os.environ.get("WINEVALUE_PIN_HOSTS", "").strip()
    if not raw:
        return
    pins = {}
    for pair in raw.split(","):
        if "=" in pair:
            host, ip = pair.split("=", 1)
            pins[host.strip()] = ip.strip()
    if not pins:
        return
    real = socket.getaddrinfo

    def shim(host, *args, **kwargs):
        return real(pins.get(host, host), *args, **kwargs)

    socket.getaddrinfo = shim


_install_dns_pins()


def strip_html(html) -> str:
    if not html:
        return ""
    return BeautifulSoup(str(html), "lxml").get_text(" ", strip=True)


class PoliteSession:
    def __init__(self, delay=0.7, timeout=30, cache_ttl=86400,
                 use_cache=True, retries=3):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT,
                               "Accept": "application/json, text/plain, */*"})
        self.delay = delay
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.use_cache = use_cache
        self.retries = retries
        self._last = 0.0
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _cache_path(self, key: str) -> str:
        h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        return os.path.join(CACHE_DIR, h + ".json")

    def _fresh(self, path: str) -> bool:
        return (os.path.exists(path)
                and (time.time() - os.path.getmtime(path)) < self.cache_ttl)

    def get_json(self, url: str, params: dict | None = None):
        key = url + "?" + json.dumps(params or {}, sort_keys=True)
        path = self._cache_path(key)
        if self.use_cache and self._fresh(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)

        attempts = max(1, self.retries)
        for attempt in range(attempts):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            last_try = attempt == attempts - 1
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout):
                self._last = time.time()
                if last_try:
                    raise
                time.sleep(backoff_seconds(attempt))
                continue
            self._last = time.time()
            if is_retryable_status(r.status_code) and not last_try:
                time.sleep(retry_after_seconds(r.headers.get("Retry-After"))
                           or backoff_seconds(attempt))
                continue
            r.raise_for_status()   # 4xx (except 429) fails immediately
            data = r.json()        # bad JSON isn't transient either
            _atomic_write_json(path, data)
            return data
        raise RuntimeError("unreachable: retries must be >= 1")


RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 60.0


def is_retryable_status(code: int) -> bool:
    return code in RETRY_STATUSES or 500 <= code < 600


def backoff_seconds(attempt: int, base: float = 1.0, cap: float = 30.0) -> float:
    """Exponential backoff: 1s, 2s, 4s, ... capped."""
    return min(cap, base * (2 ** attempt))


def retry_after_seconds(value, now: float | None = None) -> float | None:
    """Parse a Retry-After header (delta-seconds or HTTP date), capped."""
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip()
    try:
        secs = float(v)
    except ValueError:
        try:
            when = parsedate_to_datetime(v)
        except (TypeError, ValueError):
            return None
        if when is None:
            return None
        secs = when.timestamp() - (now if now is not None else time.time())
    return max(0.0, min(MAX_RETRY_AFTER, secs))


def _atomic_write_json(path: str, data) -> None:
    """Write to a temp file in the same dir, then rename, so a crash or a
    concurrent reader never sees a half-written cache file."""
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def warn_page_cap(source: str, max_pages: int) -> None:
    """Pagination loops stop at a safety cap; say so instead of truncating silently."""
    print(f"  WARNING {source}: stopped at the {max_pages}-page safety cap; "
          "results may be truncated (raise the cap if the catalog grew)")
