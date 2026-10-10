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


def test_init_db_adds_new_wine_columns_to_old_database(tmp_path):
    import sqlite3
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    old_cols = [c for c in store.COLUMNS if c != "quality_est"]
    conn.execute(f'CREATE TABLE wines ({", ".join(chr(34) + c + chr(34) for c in old_cols)}, '
                 'PRIMARY KEY (source, source_id))')
    conn.commit()
    conn.close()
    store.save([Wine(source="a", source_id="1", name="x", price_thb=500,
                     quality_est=0.5)], db)
    rows = store.read_wines(db)
    assert rows[0]["quality_est"] == 0.5


def _wine(sid, price, name=None, **kw):
    return Wine(source="s", source_id=sid, name=name or f"Wine {sid}", price_thb=price, **kw)


def test_save_across_runs_upserts_and_tracks_history(tmp_path):
    db = str(tmp_path / "t.db")
    store.save([_wine("1", 500, scraped_at="2026-01-01T00:00:00+00:00"),
                _wine("2", 800, scraped_at="2026-01-01T00:00:00+00:00")], db)
    # run 2: wine 1 unchanged, wine 2 cheaper, wine 3 new
    store.save([_wine("1", 500, scraped_at="2026-01-02T00:00:00+00:00"),
                _wine("2", 700, scraped_at="2026-01-02T00:00:00+00:00"),
                _wine("3", 900, scraped_at="2026-01-02T00:00:00+00:00")], db)
    # run 3: wine 2 back to its old price, unpriced listing of wine 1
    store.save([_wine("1", None, scraped_at="2026-01-03T00:00:00+00:00"),
                _wine("2", 800, scraped_at="2026-01-03T00:00:00+00:00")], db)

    rows = {r["source_id"]: r for r in store.read_wines(db)}
    assert sorted(rows) == ["1", "2", "3"]          # upserted, never duplicated
    assert rows["1"]["price_thb"] is None
    assert rows["2"]["price_thb"] == 800
    assert rows["1"]["scraped_at"] == "2026-01-03T00:00:00+00:00"
    assert rows["3"]["scraped_at"] == "2026-01-02T00:00:00+00:00"

    def hist(sid):
        return [h["price_thb"] for h in store.read_price_history(db, "s", sid)]
    assert hist("1") == [500]               # unchanged + missing price add nothing
    assert hist("2") == [800, 700, 800]     # every change, including back again
    assert hist("3") == [900]


def test_price_history_is_per_listing(tmp_path):
    db = str(tmp_path / "t.db")
    store.save([Wine(source="a", source_id="1", name="x", price_thb=100),
                Wine(source="b", source_id="1", name="x", price_thb=100)], db)
    store.save([Wine(source="a", source_id="1", name="x", price_thb=150),
                Wine(source="b", source_id="1", name="x", price_thb=100)], db)
    assert [h["price_thb"] for h in store.read_price_history(db, "a", "1")] == [100, 150]
    assert [h["price_thb"] for h in store.read_price_history(db, "b", "1")] == [100]


def test_price_history_lookup_index_exists(tmp_path):
    import sqlite3
    db = str(tmp_path / "t.db")
    store.save(make(100), db)
    conn = sqlite3.connect(db)
    try:
        cols = [r[2] for r in conn.execute("PRAGMA index_info(idx_price_history_item)")]
        plan = " ".join(str(r[-1]) for r in conn.execute(
            "EXPLAIN QUERY PLAN SELECT price_thb FROM price_history "
            "WHERE source=? AND source_id=? ORDER BY id DESC LIMIT 1", ("s", "1")))
    finally:
        conn.close()
    assert cols == ["source", "source_id", "id"]
    assert "idx_price_history_item" in plan


def test_init_db_adds_index_to_existing_database(tmp_path):
    import sqlite3
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE price_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "source TEXT, source_id TEXT, price_thb REAL, observed_at TEXT)")
    conn.commit()
    conn.close()
    store.save(make(100), db)
    store.save(make(100), db)   # idempotent
    conn = sqlite3.connect(db)
    names = [r[1] for r in conn.execute("PRAGMA index_list(price_history)")]
    conn.close()
    assert "idx_price_history_item" in names
