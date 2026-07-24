from models import Wine

import daily_refresh


def row(source, source_id, price=100, scraped_at="2026-06-25T00:00:00"):
    return Wine(
        source=source,
        source_id=source_id,
        name=f"{source} {source_id}",
        price_thb=price,
        scraped_at=scraped_at,
    ).to_dict()


def test_validate_sources_rejects_suspicious_drop():
    existing = [row("shop", str(index)) for index in range(10)]
    fresh = {
        "shop": [
            Wine(source="shop", source_id="new", name="Only wine", price_thb=120),
        ],
    }
    failures = {}

    accepted = daily_refresh.validate_sources(fresh, existing, failures)

    assert accepted == {}
    assert "suspicious result" in failures["shop"]


def test_merge_catalog_uses_fresh_and_retains_failed_source():
    existing = [row("fresh", "old"), row("failed", "keep")]
    replacement = Wine(
        source="fresh",
        source_id="new",
        name="Fresh wine",
        price_thb=150,
    )

    merged = daily_refresh.merge_catalog(existing, {"fresh": [replacement]})
    identities = {(wine.source, wine.source_id) for wine in merged}

    assert identities == {("fresh", "new"), ("failed", "keep")}


def test_stage_catalog_replaces_only_updated_sources(tmp_path):
    db = str(tmp_path / "wine.db")
    original = [
        Wine(source="fresh", source_id="old", name="Old", price_thb=100),
        Wine(source="failed", source_id="keep", name="Keep", price_thb=200),
    ]
    daily_refresh.store.save(original, db)
    merged = [
        Wine(source="fresh", source_id="new", name="New", price_thb=110),
        Wine(source="failed", source_id="keep", name="Keep", price_thb=200),
    ]

    daily_refresh._stage_catalog(merged, {"fresh"}, db)
    rows = daily_refresh.store.read_wines(db)

    assert {(item["source"], item["source_id"]) for item in rows} == {
        ("fresh", "new"),
        ("failed", "keep"),
    }
