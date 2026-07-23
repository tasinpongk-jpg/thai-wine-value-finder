"""Polite, cached HTTP layer shared by all scrapers.

- identifies itself with a descriptive User-Agent
- rate-limits between requests
- caches every response to disk (default 1 day) so re-runs don't re-hit the sites
- retries transient failures a few times
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import time

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

        last_err = None
        for attempt in range(self.retries):
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
                self._last = time.time()
                r.raise_for_status()
                data = r.json()
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False)
                return data
            except Exception as e:  # network, json, http
                last_err = e
                time.sleep(1.0 + attempt)
        raise last_err
