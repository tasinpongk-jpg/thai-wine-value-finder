"""scrape.run partial runs + the summary printer."""
import scrape
import store
from enrich.value import compute_scores
from models import Wine


def _scraper(*wines):
    class Fake:
        @staticmethod
        def scrape(session):
            return [Wine(**w.to_dict()) for w in wines]
    return Fake


def _rows(db):
    return {(r["source"], r["source_id"]): r for r in store.read_wines(db)}


def test_partial_run_replaces_only_scraped_shop_and_regroups(tmp_path):
    db = str(tmp_path / "wine.db")
    alpha = Wine(source="shopA", source_id="1", name="Alpha Red", price_thb=500)
    delisted = Wine(source="shopA", source_id="2", name="Delisted Rose", price_thb=600)
    zeta = Wine(source="shopB", source_id="9", name="Zeta White", price_thb=900)
    full = {"shopA": _scraper(alpha, delisted), "shopB": _scraper(zeta)}
    scrape.run(db_path=db, use_cache=False, scrapers=full)
    assert set(_rows(db)) == {("shopA", "1"), ("shopA", "2"), ("shopB", "9")}

    # shopA drops one wine and adds two; shopB isn't scraped this time
    beta = Wine(source="shopA", source_id="3", name="Beta Rose", price_thb=300)
    gamma = Wine(source="shopA", source_id="4", name="Gamma Sparkling", price_thb=700)
    partial = {"shopA": _scraper(alpha, beta, gamma), "shopB": _scraper(zeta)}
    scrape.run(sites=["shopA"], db_path=db, use_cache=False, scrapers=partial)

    rows = _rows(db)
    # delisted wine is gone, the unscraped shop's row is retained
    assert set(rows) == {("shopA", "1"), ("shopA", "3"), ("shopA", "4"), ("shopB", "9")}
    # every distinct wine has its own group: no collisions with shopB's old ids
    groups = [r["match_group"] for r in rows.values()]
    assert len(set(groups)) == len(groups)


def test_partial_run_groups_same_wine_across_shops(tmp_path):
    db = str(tmp_path / "wine.db")
    a = Wine(source="shopA", source_id="1", name="Penfolds Bin 389 2021", price_thb=2000)
    b = Wine(source="shopB", source_id="1", name="Penfolds Bin 389 2021", price_thb=2400)
    scrape.run(db_path=db, use_cache=False,
               scrapers={"shopA": _scraper(a), "shopB": _scraper(b)})
    # re-scrape only shopB; the cross-shop match with shopA must survive
    scrape.run(sites=["shopB"], db_path=db, use_cache=False,
               scrapers={"shopA": _scraper(a), "shopB": _scraper(b)})
    rows = _rows(db)
    assert rows[("shopA", "1")]["match_group"] == rows[("shopB", "1")]["match_group"]
    assert rows[("shopA", "1")]["cross_site_gap"] > 0


def test_run_with_all_shops_failing_leaves_catalog(tmp_path):
    db = str(tmp_path / "wine.db")
    keep = Wine(source="shopA", source_id="1", name="Keep", price_thb=900)
    scrape.run(db_path=db, use_cache=False, scrapers={"shopA": _scraper(keep)})

    class Broken:
        @staticmethod
        def scrape(session):
            raise RuntimeError("boom")

    assert scrape.run(db_path=db, use_cache=False, scrapers={"shopA": Broken}) == []
    assert set(_rows(db)) == {("shopA", "1")}


def test_summary_handles_missing_price_and_score(capsys):
    wines = [
        Wine(source="a", source_id="1", name="Unpriced but rated", price_thb=None,
             vivino_rating=4.8),
        Wine(source="a", source_id="2", name="Priced", price_thb=500),
        Wine(source="a", source_id="3", name=None, price_thb=700),
    ]
    compute_scores(wines)
    wines[2].value_score = None
    scrape._summary(wines, "x.db")  # used to raise TypeError on None price
    out = capsys.readouterr().out
    assert "Unpriced but rated" in out


def test_summary_counts_and_orders_top_ten(capsys):
    wines = [Wine(source="s", source_id=str(i), name=f"Wine {i}", price_thb=100.0 * (i + 1),
                  quality=0.5 if i % 2 else None, value_score=float(i))
             for i in range(12)]
    scrape._summary(wines, "x.db")
    out = capsys.readouterr().out
    assert "Saved 12 wines -> x.db" in out
    assert "with a quality rating: 6 (50%)" in out
    lines = [ln for ln in out.splitlines() if "| q=" in ln]
    assert len(lines) == 10
    assert lines[0].strip().startswith("11.0") and "Wine 11" in lines[0]
    assert "Wine 0" not in out and "Wine 1\n" not in out


def test_summary_empty_catalog(capsys):
    scrape._summary([], "x.db")
    out = capsys.readouterr().out
    assert "Saved 0 wines" in out and "(0%)" in out
