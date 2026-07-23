# Design Brief — Thai Wine Value Finder

> Hand this to a designer (or a design-focused Claude). It contains everything needed
> to redesign the UI: the product, the user, the data, the signature concept, the
> screens to design, the constraints, and **real content** to mock against.

---

## 1. What it is, in one line

A personal "wine value finder": it scrapes **5 Thai online wine shops** (~2,300 bottles),
rates each bottle, computes a **0–100 value score**, and presents it so I can quickly
find the **best bottle to buy for my money** and understand how it tastes.

## 2. Who it's for & the job to be done

- **User:** one person (me) — data-literate, new to front-end, buys wine online for
  personal drinking, on desktop mostly. Not a wine professional, but wants to feel like
  one when deciding.
- **Primary job:** "Show me bottles that are genuinely good value right now, let me
  filter to what I care about, and when one catches my eye, tell me what it tastes like
  and where it's cheapest — then send me to buy it."
- **Emotional goal:** the tool should feel like a **trusted sommelier's worksheet** —
  confident, editorial, calm. Not a noisy e-commerce grid, not a sterile admin dashboard.

## 3. What exists today (the starting point)

- **Platform: Streamlit** (a Python web-app framework). The UI is styled with injected
  custom CSS + HTML components. **The redesign must be implementable in Streamlit** —
  i.e. delivered as a design system + CSS/HTML I can drop in. (If you want to propose a
  richer interactive concept that would need a real web frontend, flag it separately as
  an optional "stretch" direction; don't make it the only deliverable.)
- **Current layout:** a masthead, a collapsible top filter bar, a 4-up metrics row, then
  **3 tabs** — Top Picks (cards), Browse & taste (table + click-to-expand detail panel),
  Insights (charts) — and a CSV export.
- **Current visual language (you may keep, refine, or replace — justify the choice):**
  - Palette: claret `#7A1F2B` (primary), brass `#B08D57` (ratings only), slate `#2F4858`
    (data/secondary), warm paper `#FBFAF7` (bg), ink `#1C1A19` (text).
  - Type: Fraunces (display serif), Inter (UI), IBM Plex Mono (prices/scores).
- **Honest assessment of the current UI:** functional and clean but a bit flat. The
  cards, detail panel, and charts don't yet feel "designed." This is what I want elevated.

## 4. The content & data to display

Every bottle has these fields (not all are present for every bottle — coverage noted):

| Field | Notes / coverage |
|---|---|
| name | always |
| shop (source) | always — Spirit House, Wine Store Asia, Wine Plus, Wishbeer, Wine Duty Free |
| price (THB) | always |
| wine type | Red / White / Rosé / Sparkling / Champagne / Dessert / Fortified / Orange |
| vintage, bottle size | often |
| country, region, grape | often |
| **Vivino rating (0–5 ⭐)** | ~37% (mostly Spirit House) |
| critic scores (e.g. "JS 95") | sparse |
| **body** (e.g. "Full-Bodied"), **ABV** | ~60% |
| **tasting notes: appearance, nose, palate, pairing** | ~50% (Spirit House + Wine Store Asia) |
| description (short blurb) | ~97% |
| producer | ~37% |
| **value score + 3 components** (see §5) | always |
| **cross-shop match** | 469 bottles are the same wine sold by 2+ shops |
| buy link | always |

**Design implication:** the detail view must degrade gracefully — a bottle with full
tasting notes should look rich; a bottle with only a description shouldn't look broken.

## 5. The signature concept — the Value Score (please make this the hero device)

The whole product hinges on one number, the **value score (0–100)**, built from three
visible parts. This is the single most important thing to visualize well — it's what
makes this tool different from a normal shop listing:

- **Quality** (45%) — the rating, normalized.
- **Price efficiency** (35%) — quality per baht (bang for buck).
- **Cross-shop discount** (20%) — how much cheaper this listing is than the same wine
  elsewhere.

Today this is shown as a small stacked bar ("value meter"). **I want a more beautiful,
more legible signature treatment** that (a) shows the score, (b) shows *why* it scores
that way (the 3 parts), and (c) feels like the brand's memorable element. Reuse it
consistently on cards and in the detail view.

## 6. Screens to design

1. **Masthead + filter bar** — title/identity, a one-line value prop, and a
   **collapsible top filter bar** containing: price range, wine type, shop, sort-by
   (value / quality / price-efficiency / discount / price), text search, min rating,
   and toggles (has rating, has tasting notes, cross-shop matches only), plus a reset.
   Goal: powerful but not overwhelming; easy to scan and reset.

2. **Top Picks (cards)** — a responsive grid of the best ~12 bottles for the current
   filter/sort. Each card: name (links out), type/country/vintage, price, rating stars,
   the **value meter**, and a one-line "why buy" (e.g. "Cheapest of 3 listings",
   "Top rated"). Make these cards genuinely attractive and scannable.

3. **Browse & taste (table → detail)** — a dense, sortable table of all filtered
   bottles; selecting a row opens a **rich detail panel**: name, badges (type, country,
   region, vintage, size, body, ABV, "cheapest of N"), big price, rating stars + critic
   chips, description, a **tasting profile** (Appearance · Nose · Palate · Pairing as
   distinct, beautiful blocks), the value meter, a **"same wine, other shops" price
   comparison table** (cheapest highlighted), and a buy button. This detail view is
   where I'd most love a step-up in craft — it should feel like a tasting card.

4. **Insights (charts)** — price-vs-rating scatter (the "value sweet spot"), value-by-
   shop, and bottles-by-type. Style the charts to match the palette (don't leave them
   default Plotly).

## 7. UX goals / problems to solve

- **Make value obvious at a glance** — I should be able to feel "this is a great deal"
  without reading numbers.
- **Reduce visual flatness** — better hierarchy, spacing, depth, and typographic rhythm.
- **The detail/tasting view should delight** — it's the payoff moment.
- **Graceful empty/missing states** — bottles without tasting notes or ratings, and the
  "no results" filter state, should still look intentional.
- **Keep it fast to scan** — this is a decision tool used repeatedly, not a one-time
  landing page. Clarity > spectacle.

## 8. Visual direction — guidance, not prescription

- **Ground it in wine, but avoid the cliché.** The generic "AI wine" look is cream
  background + big serif + terracotta accent. Please do something more specific and
  considered than that default. A risk is welcome if you can justify it.
- Keep **charts/data readable** — don't make everything red; use a cool secondary so
  data viz reads clearly.
- **Restraint:** spend boldness in one place (the value meter / tasting card). Keep the
  rest quiet and disciplined.
- Accessibility floor: legible contrast, visible focus, works down to a narrow window.

## 9. Constraints

- Implementable in **Streamlit** via custom CSS + small HTML components (cards, badges,
  the value meter, the detail panel are all HTML strings I inject). No heavy JS
  frameworks unless you're proposing the optional "stretch" web-frontend direction.
- It's a **local, single-user tool** — no login, no marketing pages, no real-time needs.
- **Desktop-first**, but should not break on a narrow window.
- Web fonts via Google Fonts are fine.

## 10. Deliverables I'd love back

1. A short **design rationale** — the concept/identity in 3–4 sentences and why it fits.
2. A **design system**: 4–6 named hex colors, a type scale (display/body/mono with
   weights & sizes), spacing/radius/shadow tokens.
3. **The signature value-meter treatment** — annotated, with the 3 components.
4. **Hi-fi mockups** (or detailed annotated wireframes if images aren't possible) of:
   the filter bar, a Top Pick card, and the **detail/tasting panel** (most important).
5. **Implementable CSS** (and HTML structure for the card + detail panel) I can paste
   into the Streamlit app, using the design tokens.
6. Notes on **empty/missing states** and **hover/selected** states.

## 11. Copy / tone

Editorial and plain — like a knowledgeable friend, not marketing. Active labels
("View at Spirit House →", "Cheapest of 3 listings"). Sentence case. No filler.

---

## 12. Real content to design against (actual bottles from the database)

Use these so mockups are realistic. Prices in THB.

**A — Top-value red, full notes**
- *Sasyr Sangiovese Syrah, Toscana IGT 2022* — Spirit House — **฿1,089**
- Red · Italy · Toscana · **Medium-Bodied** · **13.5% ABV** · Vivino **4.0 ⭐**
- **Value 77** (quality 0.80 · price-eff 0.81 · discount 0.65)
- Appearance: "A deep ruby red color with hints of purple at the rim"
- Nose: "Expressive aromas of red cherries, blackberries and plums, with subtle spice and a touch of vanilla"
- Palate: "Medium-bodied, smooth and velvety; ripe red fruits, black pepper and a hint of chocolate, with well-integrated tannins"
- Pairing: "Cheese · Pasta · Pizza · Red Meat"

**B — Best value under ฿1,000 (sparkling)**
- *Astoria Butterfly Prosecco Extra Dry (375ml)* — Spirit House — **฿473**
- Rosé/Sparkling · Italy · Treviso · **Dry** · **11% ABV** · Vivino **3.8 ⭐**
- **Value 77** (quality 0.76 · price-eff 1.00 · discount 0.39)
- Nose: "Intense, aromatic — peach, melon, ripe apple and pear, with white flowers and lemon"
- Palate: "Soft, full and harmonious; fruit-driven and refreshing with invigorating minerality"
- Pairing: "Fish"

**C — Same wine, two shops (cross-shop comparison example)**
- *Cono Sur Ocio Pinot Noir* — **Wine Duty Free ฿2,190** vs **Wine Store Asia ฿4,450 (2014)**
- The detail panel should show both, highlight ฿2,190 as cheapest, and credit the
  cross-shop discount in the value score.

**D — Sparse bottle (graceful degradation example)**
- A Wine Plus or Wine Duty Free red that has a short description but **no Vivino rating
  and no tasting notes** — design how this looks so it still feels intentional (e.g.
  "No tasting notes published for this bottle." in a quiet style), not broken.

---

### Data note for the designer
Source prices are occasionally noisy (one shop listed a ฿700 wine at ฿29.5). Not your
problem to fix, but it's why a confident, legible value treatment + the cross-shop
comparison matter — they help me sanity-check a listing at a glance.
