"""SQLite persistence: a current `wines` snapshot + an append-only `price_history`."""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import fields
from datetime import datetime

from models import Wine

_DATA = os.path.join(os.path.dirname(__file__), "data")
# Catalog (regenerable by scrape.py). Override with WINEVALUE_DB.
DEFAULT_DB = os.environ.get("WINEVALUE_DB", os.path.join(_DATA, "wine.db"))
# Personal cellar (precious — kept separate so a catalog refresh never wipes it).
# In the cloud this points at the persistent volume via WINEVALUE_CELLAR_DB.
DEFAULT_CELLAR_DB = os.environ.get("WINEVALUE_CELLAR_DB", os.path.join(_DATA, "cellar.db"))

COLUMNS = [f.name for f in fields(Wine)]
_JSON_COLS = {"critic_scores"}
_BOOL_COLS = {"match_low_confidence"}


def connect(db_path=DEFAULT_DB):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    cols_sql = ", ".join(f'"{c}"' for c in COLUMNS)
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS wines ({cols_sql}, '
        f'PRIMARY KEY (source, source_id))')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS price_history ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_id TEXT, '
        'price_thb REAL, observed_at TEXT)')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS purchases ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, source_id TEXT, name TEXT, '
        'site TEXT, price_paid REAL, quantity INTEGER, bought_date TEXT, vintage INTEGER, '
        'wine_type TEXT, notes TEXT, status TEXT DEFAULT "cellar", created_at TEXT)')
    # migration: add my_rating to pre-existing purchases tables
    cols = [r[1] for r in conn.execute("PRAGMA table_info(purchases)").fetchall()]
    if "my_rating" not in cols:
        conn.execute("ALTER TABLE purchases ADD COLUMN my_rating REAL")
    conn.commit()


def _serialize(wine: Wine) -> dict:
    d = wine.to_dict()
    for c in _JSON_COLS:
        d[c] = json.dumps(d.get(c) or [], ensure_ascii=False)
    for c in _BOOL_COLS:
        d[c] = 1 if d.get(c) else 0
    return d


def _last_price(conn, source, source_id):
    row = conn.execute(
        'SELECT price_thb FROM price_history WHERE source=? AND source_id=? '
        'ORDER BY id DESC LIMIT 1', (source, source_id)).fetchone()
    return row["price_thb"] if row else None


def save(wines, db_path=DEFAULT_DB):
    conn = connect(db_path)
    try:
        init_db(conn)
        now = datetime.now().isoformat(timespec="seconds")
        placeholders = ", ".join("?" for _ in COLUMNS)
        col_list = ", ".join(f'"{c}"' for c in COLUMNS)
        updates = ", ".join(f'"{c}"=excluded."{c}"'
                            for c in COLUMNS if c not in ("source", "source_id"))
        upsert = (f'INSERT INTO wines ({col_list}) VALUES ({placeholders}) '
                  f'ON CONFLICT(source, source_id) DO UPDATE SET {updates}')
        for w in wines:
            if not w.scraped_at:
                w.scraped_at = now
            d = _serialize(w)
            conn.execute(upsert, [d[c] for c in COLUMNS])
            if w.price_thb is not None and _last_price(conn, w.source, w.source_id) != w.price_thb:
                conn.execute(
                    'INSERT INTO price_history (source, source_id, price_thb, observed_at) '
                    'VALUES (?, ?, ?, ?)', (w.source, w.source_id, w.price_thb, now))
        conn.commit()
    finally:
        conn.close()


def _deserialize(row: sqlite3.Row) -> dict:
    d = dict(row)
    for c in _JSON_COLS:
        try:
            d[c] = json.loads(d[c]) if d.get(c) else []
        except (TypeError, json.JSONDecodeError):
            d[c] = []
    for c in _BOOL_COLS:
        d[c] = bool(d.get(c))
    return d


def read_wines(db_path=DEFAULT_DB) -> list:
    conn = connect(db_path)
    try:
        init_db(conn)
        rows = conn.execute("SELECT * FROM wines").fetchall()
        return [_deserialize(r) for r in rows]
    finally:
        conn.close()


_PURCHASE_COLS = ["source", "source_id", "name", "site", "price_paid", "quantity",
                  "bought_date", "vintage", "wine_type", "notes", "status"]


def add_purchase(purchase: dict, db_path=DEFAULT_CELLAR_DB) -> int:
    """Record a bought bottle. Returns the new purchase id."""
    conn = connect(db_path)
    try:
        init_db(conn)
        data = {c: purchase.get(c) for c in _PURCHASE_COLS}
        data["status"] = data.get("status") or "cellar"
        cols = _PURCHASE_COLS + ["created_at"]
        vals = [data[c] for c in _PURCHASE_COLS] + [
            datetime.now().isoformat(timespec="seconds")]
        ph = ", ".join("?" for _ in cols)
        cur = conn.execute(
            f'INSERT INTO purchases ({", ".join(cols)}) VALUES ({ph})', vals)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def read_purchases(db_path=DEFAULT_CELLAR_DB) -> list:
    conn = connect(db_path)
    try:
        init_db(conn)
        rows = conn.execute(
            "SELECT * FROM purchases ORDER BY bought_date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_purchase(purchase_id, db_path=DEFAULT_CELLAR_DB):
    conn = connect(db_path)
    try:
        init_db(conn)
        conn.execute("DELETE FROM purchases WHERE id=?", (purchase_id,))
        conn.commit()
    finally:
        conn.close()


def set_purchase_status(purchase_id, status, db_path=DEFAULT_CELLAR_DB):
    conn = connect(db_path)
    try:
        init_db(conn)
        conn.execute("UPDATE purchases SET status=? WHERE id=?", (status, purchase_id))
        conn.commit()
    finally:
        conn.close()


def set_purchase_rating(purchase_id, rating, db_path=DEFAULT_CELLAR_DB):
    conn = connect(db_path)
    try:
        init_db(conn)
        conn.execute("UPDATE purchases SET my_rating=? WHERE id=?", (rating, purchase_id))
        conn.commit()
    finally:
        conn.close()


def read_price_history(db_path, source, source_id) -> list:
    conn = connect(db_path)
    try:
        init_db(conn)
        rows = conn.execute(
            'SELECT price_thb, observed_at FROM price_history '
            'WHERE source=? AND source_id=? ORDER BY id', (source, source_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
