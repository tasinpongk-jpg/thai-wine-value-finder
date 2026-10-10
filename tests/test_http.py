"""PoliteSession retry/backoff/cache behaviour (no network)."""
import json
import os

import pytest
import requests

from scrapers import base


class Resp:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        self._data = data if data is not None else {"ok": True}
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "CACHE_DIR", str(tmp_path))
    sleeps = []
    monkeypatch.setattr(base.time, "sleep", lambda s: sleeps.append(s))
    s = base.PoliteSession(delay=0, use_cache=False, retries=3)
    s.sleeps = sleeps
    return s


def script(session, *responses):
    calls = []
    seq = list(responses)

    def get(url, params=None, timeout=None):
        calls.append(url)
        r = seq.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    session.s.get = get
    return calls


def test_retries_5xx_then_succeeds_with_backoff(session):
    calls = script(session, Resp(503), Resp(502), Resp(200, {"v": 1}))
    assert session.get_json("https://x/a") == {"v": 1}
    assert len(calls) == 3
    assert session.sleeps == [1.0, 2.0]          # exponential, none after success


def test_404_fails_immediately_without_retry(session):
    calls = script(session, Resp(404))
    with pytest.raises(requests.HTTPError):
        session.get_json("https://x/a")
    assert len(calls) == 1
    assert session.sleeps == []


def test_403_not_retried(session):
    calls = script(session, Resp(403))
    with pytest.raises(requests.HTTPError):
        session.get_json("https://x/a")
    assert len(calls) == 1


def test_429_honours_retry_after(session):
    calls = script(session, Resp(429, headers={"Retry-After": "7"}), Resp(200))
    session.get_json("https://x/a")
    assert len(calls) == 2
    assert session.sleeps == [7.0]


def test_no_sleep_after_last_failed_attempt(session):
    calls = script(session, Resp(500), Resp(500), Resp(500))
    with pytest.raises(requests.HTTPError):
        session.get_json("https://x/a")
    assert len(calls) == 3
    assert session.sleeps == [1.0, 2.0]          # not 3 sleeps


def test_connection_errors_retried_then_raised(session):
    calls = script(session, requests.ConnectionError("dns"), requests.Timeout("slow"),
                   requests.ConnectionError("dns"))
    with pytest.raises(requests.ConnectionError):
        session.get_json("https://x/a")
    assert len(calls) == 3
    assert session.sleeps == [1.0, 2.0]


def test_bad_json_not_retried(session):
    class Bad(Resp):
        def json(self):
            raise ValueError("not json")
    calls = script(session, Bad(200))
    with pytest.raises(ValueError):
        session.get_json("https://x/a")
    assert len(calls) == 1


def test_retry_after_parsing():
    assert base.retry_after_seconds("5") == 5
    assert base.retry_after_seconds("9999") == base.MAX_RETRY_AFTER
    assert base.retry_after_seconds("-3") == 0
    assert base.retry_after_seconds(None) is None
    assert base.retry_after_seconds("garbage") is None
    # HTTP-date form, 10s after "now"
    assert base.retry_after_seconds("Thu, 01 Jan 1970 00:00:10 GMT", now=0) == 10


def test_cache_written_atomically_and_reused(session, tmp_path):
    script(session, Resp(200, {"v": 2}))
    session.get_json("https://x/a", {"p": 1})
    files = os.listdir(tmp_path)
    assert len(files) == 1 and not files[0].startswith(".tmp-")
    with open(tmp_path / files[0], encoding="utf-8") as fh:
        assert json.load(fh) == {"v": 2}
    session.use_cache = True
    script(session)                     # any network call would IndexError
    assert session.get_json("https://x/a", {"p": 1}) == {"v": 2}


def test_atomic_write_leaves_no_temp_on_failure(tmp_path):
    with pytest.raises(TypeError):
        base._atomic_write_json(str(tmp_path / "x.json"), {"bad": object()})
    assert os.listdir(tmp_path) == []
