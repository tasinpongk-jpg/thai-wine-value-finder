import store


def _p(**kw):
    base = dict(source="spirithouse", source_id="123", name="Sasyr Sangiovese",
                site="Spirit House", price_paid=1089.0, quantity=2,
                bought_date="2026-06-25", vintage=2022, wine_type="Red", notes="for dinner")
    base.update(kw)
    return base


def test_add_and_read_purchase(tmp_path):
    db = str(tmp_path / "t.db")
    pid = store.add_purchase(_p(), db)
    rows = store.read_purchases(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == pid
    assert r["name"] == "Sasyr Sangiovese"
    assert r["price_paid"] == 1089.0
    assert r["quantity"] == 2
    assert r["status"] == "cellar"          # default


def test_multiple_purchases_kept_separately(tmp_path):
    db = str(tmp_path / "t.db")
    store.add_purchase(_p(), db)
    store.add_purchase(_p(name="Astoria Prosecco", source_id="999", quantity=1), db)
    rows = store.read_purchases(db)
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"Sasyr Sangiovese", "Astoria Prosecco"}


def test_delete_purchase(tmp_path):
    db = str(tmp_path / "t.db")
    pid = store.add_purchase(_p(), db)
    store.delete_purchase(pid, db)
    assert store.read_purchases(db) == []


def test_set_status_to_drunk(tmp_path):
    db = str(tmp_path / "t.db")
    pid = store.add_purchase(_p(), db)
    store.set_purchase_status(pid, "drunk", db)
    assert store.read_purchases(db)[0]["status"] == "drunk"


def test_read_purchases_empty(tmp_path):
    db = str(tmp_path / "t.db")
    assert store.read_purchases(db) == []


def test_set_and_read_my_rating(tmp_path):
    db = str(tmp_path / "t.db")
    pid = store.add_purchase(_p(), db)
    assert store.read_purchases(db)[0]["my_rating"] is None   # default
    store.set_purchase_rating(pid, 4.5, db)
    assert store.read_purchases(db)[0]["my_rating"] == 4.5
