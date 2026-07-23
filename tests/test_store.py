import store
from models import Wine


def make(price, name="Wine A", scores=None):
    return [Wine(source="s", source_id="1", name=name, price_thb=price,
                 wine_type="Red", value_score=50.0,
                 critic_scores=scores or [{"critic": "JS", "score": 92}])]


def test_save_and_read_roundtrip(tmp_path):
    db = str(tmp_path / "t.db")
    store.save(make(100), db)
    rows = store.read_wines(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["price_thb"] == 100
    assert r["wine_type"] == "Red"
    # critic_scores round-trips back to a list of dicts
    assert r["critic_scores"] == [{"critic": "JS", "score": 92}]


def test_upsert_updates_not_duplicates(tmp_path):
    db = str(tmp_path / "t.db")
    store.save(make(100), db)
    store.save(make(120, name="Wine A renamed"), db)
    rows = store.read_wines(db)
    assert len(rows) == 1
    assert rows[0]["price_thb"] == 120
    assert rows[0]["name"] == "Wine A renamed"


def test_price_history_grows_on_change(tmp_path):
    db = str(tmp_path / "t.db")
    store.save(make(100), db)
    store.save(make(120), db)
    hist = store.read_price_history(db, "s", "1")
    assert [h["price_thb"] for h in hist] == [100, 120]


def test_price_history_dedups_unchanged(tmp_path):
    db = str(tmp_path / "t.db")
    store.save(make(100), db)
    store.save(make(100), db)
    hist = store.read_price_history(db, "s", "1")
    assert len(hist) == 1
