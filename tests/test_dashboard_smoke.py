"""Streamlit AppTest smoke tests: the dashboard runs, and cellar access modes work."""
import os

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import store  # noqa: E402
from enrich.value import compute_scores  # noqa: E402
from models import Wine  # noqa: E402


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    db, cellar = str(tmp_path / "wine.db"), str(tmp_path / "cellar.db")
    wines = [
        Wine(source="spirithouse", source_id="1", name="Test Shiraz", price_thb=900,
             size_ml=750, wine_type="Red", vivino_rating=4.1, country="Australia",
             scraped_at="2026-10-10T00:00:00+00:00", match_group=0),
        Wine(source="wishbeer", source_id="2", name="Test Prosecco", price_thb=650,
             size_ml=750, wine_type="Sparkling", scraped_at="2026-10-10T00:00:00+00:00",
             match_group=1),
    ]
    compute_scores(wines)
    store.save(wines, db)
    store.add_purchase({"source": "spirithouse", "source_id": "1", "name": "Test Shiraz",
                        "site": "Spirit House", "price_paid": 900, "quantity": 2,
                        "bought_date": "2026-10-01"}, cellar)
    # dashboard.py reads these module attributes at run time (same interpreter)
    monkeypatch.setattr(store, "DEFAULT_DB", db)
    monkeypatch.setattr(store, "DEFAULT_CELLAR_DB", cellar)
    monkeypatch.delenv("WINEVALUE_PUBLIC_MODE", raising=False)
    monkeypatch.delenv("WINEVALUE_CELLAR_PASSWORD", raising=False)
    return monkeypatch


DASHBOARD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "dashboard.py")


def run_app(**secrets):
    at = AppTest.from_file(DASHBOARD, default_timeout=60)
    for k, v in secrets.items():
        at.secrets[k] = v
    return at.run()


def labels(at):
    return [t.label for t in at.tabs]


def all_text(at):
    return " ".join(str(m.value) for m in at.markdown)


def test_dashboard_runs_and_cellar_open_locally(app_env):
    at = run_app()
    assert not at.exception
    assert labels(at) == ["🏆 Top Picks", "🔍 Browse & taste", "🍷 My Cellar (1)", "📊 Insights"]
    assert "Test Shiraz" in all_text(at)


def test_public_mode_hides_cellar(app_env):
    app_env.setenv("WINEVALUE_PUBLIC_MODE", "1")
    at = run_app()
    assert not at.exception
    assert "🍷 My Cellar" in labels(at)
    assert not any("(1)" in label for label in labels(at))
    assert "Cellar tracking is disabled on the public site" in all_text(at)
    assert "Test Shiraz" in all_text(at)   # catalog still visible


def test_public_mode_via_secrets(app_env):
    at = run_app(public_mode=True)
    assert not at.exception
    assert "Cellar tracking is disabled on the public site" in all_text(at)


def test_password_locks_cellar_until_correct(app_env):
    app_env.setenv("WINEVALUE_CELLAR_PASSWORD", "s3cret")
    at = run_app()
    assert not at.exception
    assert "password-protected" in all_text(at)
    assert not any("(1)" in label for label in labels(at))

    at.text_input(key="cellar_pw").input("wrong")
    form_submit = [b for b in at.button if b.label == "Unlock"][0]
    form_submit.click().run()
    assert "password-protected" in all_text(at)
    assert any("Wrong password" in str(e.value) for e in at.error)

    at.text_input(key="cellar_pw").input("s3cret")
    [b for b in at.button if b.label == "Unlock"][0].click().run()
    assert not at.exception
    assert "🍷 My Cellar (1)" in labels(at)
