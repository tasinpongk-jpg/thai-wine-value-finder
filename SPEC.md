# Thai Wine Value Finder — SPEC

A small Python project that scrapes 5 Thai online wine retailers, enriches each bottle
with ratings, computes a 0–100 **value score**, and shows everything in a Streamlit
dashboard for finding the best bottles to buy.

This is **personal research**. Scraping is polite (rate-limited, identifies itself,
caches responses) and uses each site's own public data API where one exists.

---

## Two commands

```bash
python scrape.py            # gather/refresh data -> data/wine.db   (run when you want fresh data)
streamlit run dashboard.py  # view it                                (instant, never waits on scraping)
```

They are deliberately separate so viewing is always fast.

---

## The 5 sites & their VERIFIED data sources

All five expose a clean structured JSON API — **no HTML parsing required**. Recipes below
were each tested live (2026-06-24).

| # | Site | Platform | Endpoint (paginate until short/empty) |
|---|------|----------|----------------------------------------|
| 1 | winedutyfree.com | WooCommerce | `GET /wp-json/wc/store/v1/products?per_page=100&page=N` |
| 2 | Wishbeer | Shopify | `GET https://www.wishbeer.com/collections/wine/products.json?limit=250&page=N` |
| 3 | Wine Store Asia | Magento 2 | `GET https://www.winestoreasia.com/rest/V1/products?searchCriteria[pageSize]=250&searchCriteria[currentPage]=N` |
| 4 | Wine Plus | WooCommerce | `GET https://wineplus.co.th/wp-json/wc/store/v1/products?per_page=100&page=N` |
| 5 | Spirit House | WooCommerce | `GET https://spirithouse.com/wp-json/wc/store/v1/products?category=50&per_page=100&page=N` |

Approx total catalog: **~2,000 wines** (WDF ~150, Wishbeer 286, WineStoreAsia ~589, WinePlus ~400, SpiritHouse ~850).

### Per-site field notes

**WooCommerce (winedutyfree, wineplus, spirithouse)** — each product object:
- `name`, `permalink`, `sku`
- price: `prices.price` is an **integer in satang** → divide by `10 ** prices.currency_minor_unit` (usually /100). Also `regular_price`, `sale_price`, `on_sale`.
- `categories[].name` — split into wine type vs country (heuristic).
- `attributes[]` — list of `{name/taxonomy, terms[].name}`. Spirit House uses `pa_wine-type`, `pa_vintage`, `pa_volume`, `pa_country`, `pa_region`, `pa_varietals`, **`pa_vivino-rating`** (present on ~100% of its wines), `pa_style`.
- `average_rating`, `review_count` (WooCommerce store reviews — usually 0).
- `short_description`, `description` (HTML; strip tags). Critic scores, when present, live here.
- WinePlus: `X-WP-Total` header is unreliable → paginate until a short page.

**Shopify (Wishbeer)** — each product in `products[]`:
- `title`, `variants[0].price` (string baht, e.g. `"1159.00"`).
- `tags[]` carry `Type:`, `Country:`, `Region:`, `Grape:`, `World:`.
- size & vintage parsed by regex on `title`. No critic scores. Use the **www** host.
- Pagination: stop when `products` array < limit or empty.

**Magento 2 (Wine Store Asia)** — `items[]`, body has `total_count`:
- `name`, `price` (plain THB number), `sku`.
- Wine attributes live in `custom_attributes[]` as **dropdown integer IDs**. Resolve once via
  `GET /rest/V1/products/attributes/{code}` → `.options[]={value,label}`, then map.
  Codes: `wine_type`, `wine_bottle_size`, `country` (or `country_of_manufacture`=ISO), `wine_province_area`, `wine_grape_varieties`. `vintage` is a plain value (no lookup).
- Filter to wine: `wine_type` notnull. No critic scores.

---

## Ratings (two realistic sources, degrade gracefully)

1. **Critic scores from product text** (`enrich/critic_scores.py`): regex over name + descriptions
   for `JS 95`, `WS 92`, `RP 90`, `WA 93`, `WE`, `JD`, `Decanter`, `Vinous`, `90 points`, `90/100`, `90+`.
   Free and reliable *when present* — but across these sites it is **sparse** (often <5%).
2. **Vivino community stars** (`enrich/vivino.py`): best-effort lookup by name+vintage.
   Vivino blocks scrapers, so coverage is partial; cache results; on miss the wine still appears
   marked "no Vivino match." **Nothing breaks.**
   - Bonus: **Spirit House already provides a Vivino rating per wine** (`pa_vivino-rating`) — use it directly, no lookup.

`quality` = best available normalized rating, in priority: site-provided Vivino → Vivino lookup → critic score → none.

---

## The value score (0–100, all parts visible)

Each wine gets a combined score from three components; the dashboard can re-sort by any single one.

| Component | Meaning | How |
|---|---|---|
| **Quality** | how good the wine is | normalized rating 0–1 (Vivino stars/5, or critic pts mapped 80–100 → 0–1) |
| **Price efficiency** | quality per baht | quality ÷ price, normalized across the dataset (log-scaled) |
| **Cross-site gap** | how much cheaper this listing is | (median price for the same wine across sites − this price) / median, clipped ≥0 |

`value_score = 100 * (0.45*quality + 0.35*price_efficiency + 0.20*cross_site_gap)`.
Wines with no quality signal get a quality of `None` and are scored on price efficiency + gap only
(and flagged), so they still appear but rank lower.

## Cross-site matching (`enrich/match.py`)

Fuzzy match the same wine across sites by normalized `name + vintage + size` using rapidfuzz
`token_sort_ratio` ≥ 88. Low-confidence matches are **flagged, not hidden**. Produces a
`match_group` id used by the cross-site-gap component and a "cheapest source" badge.

---

## Architecture

```
wine-value/
├─ models.py            # Wine dataclass (normalized schema)
├─ sources.py           # per-site config (endpoint, host, ids)
├─ scrapers/
│   ├─ base.py          # polite HTTP session (UA, retry, rate-limit, disk cache)
│   ├─ winedutyfree.py  ├─ wishbeer.py     ├─ winestoreasia.py
│   ├─ wineplus.py      └─ spirithouse.py  # each: scrape() -> list[Wine]
├─ enrich/
│   ├─ normalize.py     # price/size/type/vintage canonicalization
│   ├─ critic_scores.py # extract critic scores from text
│   ├─ vivino.py        # best-effort Vivino lookup (cached)
│   ├─ match.py         # cross-site fuzzy matching
│   └─ value.py         # compute 0–100 score
├─ store.py             # SQLite: wines snapshot + price_history (keeps price over time)
├─ scrape.py            # orchestrator (run this to refresh)
├─ dashboard.py         # Streamlit app (run this to view)
├─ data/                # wine.db + http cache (gitignored)
├─ tests/               # pytest: pure logic + fixture-based parser tests
└─ requirements.txt
```

## Normalized `Wine` schema

`source, source_id, name, price_thb, vintage, wine_type, size_ml, country, region, grape,
url, image, critic_scores(list), vivino_rating, vivino_count, review_rating, review_count,
quality, price_efficiency, cross_site_gap, value_score, match_group, scraped_at`

Canonical `wine_type` ∈ {Red, White, Rosé, Sparkling, Champagne, Dessert, Fortified, Orange, Other}.

## Politeness & caveats

- Browser User-Agent, ~0.5–1s between paged requests, short timeouts, on-disk response cache
  (re-run within the same day won't re-hit the sites).
- These public APIs may be locked down at any time; scrapers degrade gracefully (a failing site
  is logged and skipped, the rest still produce a dashboard).
- Personal-use research only.
