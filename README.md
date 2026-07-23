# 🍷 Thai Wine Value Finder

Scrapes **5 Thai online wine shops**, rates every bottle, computes a **0–100 value
score**, and shows it all in a dashboard so you can find the best bottles to buy.

Built for personal research. It uses each shop's own public data API (no fragile
HTML scraping), is polite (rate-limited, cached, identifies itself), and degrades
gracefully — if one shop is down, the rest still work.

Public app: https://thai-wine-value-finder-public.tasinpong-k.workers.dev

| Shop | Wines | Source |
|------|------:|--------|
| Spirit House | ~850 | WooCommerce API (+ built-in Vivino ratings) |
| Wine Store Asia | ~590 | Magento API |
| Wine Plus | ~400 | WooCommerce API |
| Wishbeer | ~290 | Shopify API |
| Wine Duty Free | ~150 | WooCommerce API |

Currently **~2,300 bottles**, ~2,000 distinct after matching the same wine across shops.

---

## Quick start

```bash
pip install -r requirements.txt   # one time

python scrape.py                  # 1) gather + score everything -> data/wine.db
streamlit run dashboard.py        # 2) open the dashboard in your browser
```

That's the whole thing — **two commands**. `scrape.py` does the slow web work and
saves to a small database; `dashboard.py` just reads that database, so viewing is
always instant. Re-run `scrape.py` whenever you want fresh prices.

### What the dashboard does
- **Top Picks** — best-value bottles as cards (with bottle photos) and a "Value Seal".
- **Browse & taste** — every bottle in a sortable list; click one to open its
  **tasting card** (photo, ratings, the value seal, nose/palate/appearance/pairing,
  and a "same wine, other shops" price comparison).
- **My Cellar** — tap **＋ Add to my cellar** on any tasting card to record a bottle you
  bought (quantity, price paid, date, notes). The My Cellar tab tracks bottles on hand,
  total spent, and what you've opened. Stored in the same SQLite database.
- **Insights** — price-vs-rating sweet-spot chart and value-by-shop.

---

## What the value score means

Every wine gets a score out of 100 built from three parts (you can re-sort the
dashboard by any single part):

- **Quality** — the wine's rating, normalized to 0–1 (Vivino stars, or critic
  points like "JS 95" when a shop prints them).
- **Price efficiency** — quality per baht. Bang for buck.
- **Cross-site discount** — how much cheaper this listing is than the *same wine*
  on the other shops.

Score = `45% quality + 35% price-efficiency + 20% cross-site discount`.

Wines with no rating still show up — they're just scored on price/discount only,
so they rank a bit lower (and are easy to filter out).

### Where ratings come from
- **Spirit House** publishes a Vivino rating for nearly every wine — used directly.
- Other shops rarely print scores, so quality is sparse there. `scrape.py --vivino N`
  will *try* to look up Vivino ratings by name, but Vivino blocks bots, so it's
  best-effort and off by default (it stops early if it sees it's blocked).

---

## Useful commands

```bash
python scrape.py --no-cache              # ignore the 1-day cache, fetch fresh
python scrape.py --sites wishbeer        # only some shops
python scrape.py --vivino 200            # also try up to 200 Vivino lookups
python -m pytest -q                      # run the test suite (64 tests)
```

## Project layout

```
scrape.py          run this to gather + score data
dashboard.py       run this to view (Streamlit)
sources.py         per-shop config (endpoints)
models.py          the Wine data shape
scrapers/          one file per shop + shared helpers
enrich/            normalize, critic scores, Vivino, matching, value score
store.py           SQLite (current prices + price history over time)
data/              tracked public wine catalog + private local cellar and cache
tests/             pytest (pure logic + fixture-based parser tests)
SPEC.md            full design + the verified scraping recipes
```

## Notes & caveats

- **Refresh is manual** — run `scrape.py` when you want new data. Prices are kept
  in a history table, so you can later chart how a wine's price moved.
- **Flaky DNS?** If a shop won't resolve on your network, you can pin its IP:
  `WINEVALUE_PIN_HOSTS="www.wishbeer.com=23.227.38.74" python scrape.py`.
  Not needed on a normal connection.
- These public APIs could change or be locked down at any time. If a shop's scraper
  breaks, it's logged and skipped — the dashboard still works with the other shops.
- Personal-use research only.

## Cloudflare deployment

The public release is a read-only static catalog on Cloudflare Workers Static
Assets, compatible with the Workers Free plan. `build_static.py` exports the
checked-in SQLite snapshot to browser-ready JSON. Search, filters, ranking,
tasting cards, cross-shop comparisons, insights, and CSV export run in the browser.

My Cellar stays in the local Streamlit deployment so anonymous visitors cannot
share or overwrite one SQLite purchase history. `data/cellar.db`, caches, secrets,
design sources, and local build artifacts are excluded from Git and the image.

```bash
npm install
npm run build:static
npm run deploy
```

`npm run deploy` rebuilds the public JSON snapshot, uploads the static assets,
and prints the public `workers.dev` URL.

The full Streamlit app still runs locally or on any container host:

```bash
npm run docker:build
docker run --rm -p 8501:8501 thai-wine-value-finder
```
