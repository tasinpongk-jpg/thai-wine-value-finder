const state = {
  wines: [],
  filtered: [],
  byId: new Map(),
  groups: new Map(),
  selectedTypes: new Set(),
  selectedShops: new Set(),
  page: 1,
  pageSize: 20,
  tab: "top",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const fmtNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const fmtPrice = (value) => value == null || Number.isNaN(Number(value)) ? "—" : fmtNumber.format(Number(value));
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[char]);
const safeUrl = (value) => {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch { return ""; }
};
const proxiedImage = (url, width = 220) => {
  const safe = safeUrl(url);
  return safe ? `https://wsrv.nl/?url=${encodeURIComponent(safe)}&w=${width}&output=webp&q=82` : "";
};
const wineId = (wine) => `${wine.source}::${wine.source_id}`;
const value = (wine, field) => {
  const raw = wine[field];
  return raw == null || raw === "" || !Number.isFinite(Number(raw)) ? null : Number(raw);
};

const colors = {
  Red: "#b23047", White: "#d8c27a", Rosé: "#e0828f", Sparkling: "#c8a24c",
  Champagne: "#c8a24c", Dessert: "#c98a3a", Fortified: "#8a4b3a", Orange: "#c97a33", Other: "#75685e",
};
const shopColors = {
  "Spirit House": "#b23047", "Wine Store Asia": "#7fa0b4", "Wine Plus": "#c8a24c",
  Wishbeer: "#9c6b74", "Wine Duty Free": "#8a7c70",
};
const sortLabels = {
  value_score: "value", quality: "quality", price_efficiency: "price efficiency",
  cross_site_gap: "cross-shop discount", price_thb: "price",
};

function initDerivedData() {
  for (const wine of state.wines) {
    state.byId.set(wineId(wine), wine);
    if (wine.match_group != null) {
      const key = String(wine.match_group);
      if (!state.groups.has(key)) state.groups.set(key, []);
      state.groups.get(key).push(wine);
    }
  }
  for (const wine of state.wines) {
    const peers = wine.match_group == null ? [wine] : state.groups.get(String(wine.match_group));
    wine.listings = peers?.length || 1;
    const prices = (peers || []).map((item) => value(item, "price_thb")).filter((item) => item != null);
    wine.cheapest = prices.length ? Math.min(...prices) : null;
    wine.isCheapest = wine.listings > 1 && value(wine, "price_thb") === wine.cheapest;
    wine.hasTasting = [wine.nose, wine.palate, wine.appearance, wine.pairing].some(Boolean);
  }
}

function makeChips(target, values, selected, kind) {
  target.innerHTML = values.map((item) => `<button type="button" class="chip" aria-pressed="false" data-chip-kind="${kind}" data-chip-value="${esc(item)}">${esc(item)}</button>`).join("");
  target.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-chip-value]");
    if (!button) return;
    const item = button.dataset.chipValue;
    selected.has(item) ? selected.delete(item) : selected.add(item);
    button.setAttribute("aria-pressed", selected.has(item) ? "true" : "false");
    applyFilters();
  });
}

function setupControls() {
  const types = [...new Set(state.wines.map((wine) => wine.wine_type).filter(Boolean))].sort();
  const shops = [...new Set(state.wines.map((wine) => wine.site).filter(Boolean))].sort();
  makeChips($("#typeChips"), types, state.selectedTypes, "type");
  makeChips($("#shopChips"), shops, state.selectedShops, "shop");
  ["#minPrice", "#maxPrice", "#sortSelect", "#ratingSelect", "#hasRating", "#hasTasting", "#crossShop"]
    .forEach((selector) => $(selector).addEventListener("change", applyFilters));
  let searchTimer;
  $("#searchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 120);
  });
  $("#resetButton").addEventListener("click", resetFilters);
  $("#prevPage").addEventListener("click", () => { state.page -= 1; renderBrowse(); scrollPanelTop(); });
  $("#nextPage").addEventListener("click", () => { state.page += 1; renderBrowse(); scrollPanelTop(); });
  $("#csvButton").addEventListener("click", exportCsv);
  $("#dialogClose").addEventListener("click", () => $("#detailDialog").close());
  $("#detailDialog").addEventListener("click", (event) => {
    if (event.target === $("#detailDialog")) $("#detailDialog").close();
  });
  $$(".tabs button").forEach((button) => button.addEventListener("click", () => setTab(button.dataset.tab)));
  document.addEventListener("click", (event) => {
    const detailButton = event.target.closest("[data-detail]");
    if (detailButton) showDetail(detailButton.dataset.detail);
  });
  document.addEventListener("error", (event) => {
    const image = event.target;
    if (!(image instanceof HTMLImageElement) || !image.dataset.fallback) return;
    const fallback = document.createElement("div");
    fallback.className = `${image.className} img-fallback`;
    fallback.textContent = image.dataset.fallback;
    image.replaceWith(fallback);
  }, true);
}

function resetFilters() {
  $("#minPrice").value = 0;
  $("#maxPrice").value = 5000;
  $("#searchInput").value = "";
  $("#sortSelect").value = "value_score";
  $("#ratingSelect").value = "0";
  $("#hasRating").checked = false;
  $("#hasTasting").checked = false;
  $("#crossShop").checked = false;
  state.selectedTypes.clear();
  state.selectedShops.clear();
  $$(".chip[aria-pressed]").forEach((button) => button.setAttribute("aria-pressed", "false"));
  applyFilters();
}

function applyFilters() {
  const minPrice = Number($("#minPrice").value) || 0;
  const maxPrice = Number($("#maxPrice").value) || Number.MAX_SAFE_INTEGER;
  const minRating = Number($("#ratingSelect").value) || 0;
  const search = $("#searchInput").value.trim().toLocaleLowerCase();
  const sort = $("#sortSelect").value;
  state.filtered = state.wines.filter((wine) => {
    const price = value(wine, "price_thb");
    if (price == null || price < minPrice || price > maxPrice) return false;
    if (state.selectedTypes.size && !state.selectedTypes.has(wine.wine_type)) return false;
    if (state.selectedShops.size && !state.selectedShops.has(wine.site)) return false;
    if (minRating && (value(wine, "vivino_rating") || 0) < minRating) return false;
    if ($("#hasRating").checked && value(wine, "quality") == null) return false;
    if ($("#hasTasting").checked && !wine.hasTasting) return false;
    if ($("#crossShop").checked && wine.listings <= 1) return false;
    if (search) {
      const haystack = [wine.name, wine.producer, wine.grape, wine.country, wine.region, wine.site]
        .filter(Boolean).join(" ").toLocaleLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
  state.filtered.sort((a, b) => {
    const av = value(a, sort);
    const bv = value(b, sort);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return sort === "price_thb" ? av - bv : bv - av;
  });
  state.page = 1;
  renderAll();
}

function renderAll() {
  renderMetrics();
  renderTop();
  renderBrowse();
  renderInsights();
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function renderMetrics() {
  const distinct = new Set(state.filtered.map((wine) => wine.match_group == null ? wineId(wine) : `g:${wine.match_group}`));
  const rated = state.filtered.filter((wine) => value(wine, "quality") != null).length;
  const med = median(state.filtered.map((wine) => value(wine, "price_thb")).filter((item) => item != null));
  $("#metricBottles").textContent = fmtNumber.format(state.filtered.length);
  $("#metricDistinct").textContent = fmtNumber.format(distinct.size);
  $("#metricRated").textContent = fmtNumber.format(rated);
  $("#metricMedian").textContent = med == null ? "—" : `฿${fmtPrice(med)}`;
}

function imageMarkup(wine, className = "wine-img") {
  const image = proxiedImage(wine.image);
  if (!image) return `<div class="${className} img-fallback">${esc((wine.wine_type || "?").slice(0, 1))}</div>`;
  return `<img class="${className}" src="${esc(image)}" alt="" loading="lazy" data-fallback="${esc((wine.wine_type || "?").slice(0, 1))}">`;
}

function ratingMarkup(wine) {
  const rating = value(wine, "vivino_rating");
  return rating == null ? '<span class="rating missing">Unrated</span>' : `<span class="rating">★ ${rating.toFixed(1)}</span>`;
}

function whyText(wine) {
  if (wine.isCheapest) return `Cheapest of ${wine.listings} listings`;
  const quality = value(wine, "quality");
  const efficiency = value(wine, "price_efficiency");
  if (quality != null && quality >= .8) return "High quality score";
  if (efficiency != null && efficiency >= .7) return "Strong quality per baht";
  return "Catalog pick";
}

function cardMarkup(wine) {
  const score = value(wine, "value_score") || 0;
  const quality = (value(wine, "quality") || 0) * 45;
  const efficiency = (value(wine, "price_efficiency") || 0) * 35;
  const discount = (value(wine, "cross_site_gap") || 0) * 20;
  const meta = [wine.wine_type, wine.country, wine.vintage].filter((item) => item != null && item !== "").join(" · ");
  const url = safeUrl(wine.url);
  return `<article class="wine-card">
    <div class="card-head">${imageMarkup(wine)}<div><div class="eyebrow">${esc(meta)}</div><div class="wine-name">${esc(wine.name)}</div></div></div>
    <div class="price-rating"><span class="price"><small>฿</small>${fmtPrice(wine.price_thb)}</span>${ratingMarkup(wine)}</div>
    <div class="value-row"><strong>${score.toFixed(0)}</strong><span>VALUE</span></div>
    <div class="value-track"><i style="width:${quality}%;background:#c8a24c"></i><i style="width:${efficiency}%;background:#b23047"></i><i style="width:${discount}%;background:#7fa0b4"></i></div>
    <div class="why">${esc(whyText(wine))}</div>
    <div class="card-actions"><button type="button" class="secondary" data-detail="${esc(wineId(wine))}">Tasting card</button>${url ? `<a class="link-button" href="${esc(url)}" target="_blank" rel="noopener noreferrer">View shop</a>` : ""}</div>
  </article>`;
}

function renderTop() {
  $("#topNote").textContent = state.filtered.length ? `Best ${Math.min(12, state.filtered.length)} by ${sortLabels[$("#sortSelect").value]}.` : "";
  $("#topCards").innerHTML = state.filtered.length ? state.filtered.slice(0, 12).map(cardMarkup).join("") : '<div class="empty">No bottles match these filters.</div>';
}

function browseRowMarkup(wine) {
  const meta = [wine.country, wine.region, wine.vintage].filter((item) => item != null && item !== "").join(" · ");
  return `<div class="browse-row">
    <div><div class="browse-name">${esc(wine.name)}</div><div class="browse-meta">${esc(meta)}</div></div>
    <div class="browse-type"><span class="type-dot" style="background:${colors[wine.wine_type] || colors.Other}"></span>${esc(wine.wine_type)}</div>
    <div class="browse-price">฿${fmtPrice(wine.price_thb)}</div>
    <div class="browse-value">${(value(wine, "value_score") || 0).toFixed(0)}</div>
    <button type="button" class="secondary" data-detail="${esc(wineId(wine))}">View</button>
  </div>`;
}

function renderBrowse() {
  const pages = Math.max(1, Math.ceil(state.filtered.length / state.pageSize));
  state.page = Math.max(1, Math.min(state.page, pages));
  const start = (state.page - 1) * state.pageSize;
  const end = Math.min(start + state.pageSize, state.filtered.length);
  $("#browseNote").textContent = state.filtered.length ? `Showing ${start + 1}–${end} of ${fmtNumber.format(state.filtered.length)}` : "No bottles match these filters.";
  $("#pageLabel").textContent = `${state.page} / ${pages}`;
  $("#prevPage").disabled = state.page <= 1;
  $("#nextPage").disabled = state.page >= pages;
  $("#browseList").innerHTML = state.filtered.slice(start, end).map(browseRowMarkup).join("");
}

function barChartMarkup(items, maxValue, formatter = (item) => fmtNumber.format(item)) {
  return items.map(([label, amount], index) => `<div class="bar-item">
    <span>${esc(label)}</span><div class="bar-track"><div class="bar-fill" style="width:${maxValue ? amount / maxValue * 100 : 0}%;background:${Object.values(shopColors)[index % 5]}"></div></div><span class="bar-value">${formatter(amount)}</span>
  </div>`).join("");
}

function renderInsights() {
  const byShop = new Map();
  const byType = new Map();
  for (const wine of state.filtered) {
    const shop = byShop.get(wine.site) || [];
    shop.push(value(wine, "value_score") || 0);
    byShop.set(wine.site, shop);
    byType.set(wine.wine_type || "Other", (byType.get(wine.wine_type || "Other") || 0) + 1);
  }
  const shopAverages = [...byShop].map(([key, values]) => [key, values.reduce((a, b) => a + b, 0) / values.length]).sort((a, b) => b[1] - a[1]);
  const typeCounts = [...byType].sort((a, b) => b[1] - a[1]);
  $("#shopBars").innerHTML = barChartMarkup(shopAverages, Math.max(1, ...shopAverages.map((item) => item[1])), (item) => item.toFixed(1));
  $("#typeBars").innerHTML = barChartMarkup(typeCounts, Math.max(1, ...typeCounts.map((item) => item[1])));
  $("#scatterChart").innerHTML = scatterMarkup(state.filtered.filter((wine) => value(wine, "vivino_rating") != null && value(wine, "price_thb") > 0));
}

function scatterMarkup(wines) {
  const width = 720, height = 340, left = 54, right = 18, top = 16, bottom = 40;
  const plotW = width - left - right, plotH = height - top - bottom;
  const minP = Math.log10(250), maxP = Math.log10(50000), minR = 2.5, maxR = 5;
  const x = (price) => left + (Math.log10(Math.max(250, Math.min(50000, price))) - minP) / (maxP - minP) * plotW;
  const y = (rating) => top + (maxR - Math.max(minR, Math.min(maxR, rating))) / (maxR - minR) * plotH;
  const xTicks = [250, 500, 1000, 2500, 5000, 10000, 50000];
  const yTicks = [3, 3.5, 4, 4.5, 5];
  const grid = [
    ...xTicks.map((tick) => `<line class="grid-line" x1="${x(tick)}" y1="${top}" x2="${x(tick)}" y2="${height-bottom}"/><text class="axis-label" x="${x(tick)}" y="${height-15}" text-anchor="middle">${tick >= 1000 ? `${tick/1000}k` : tick}</text>`),
    ...yTicks.map((tick) => `<line class="grid-line" x1="${left}" y1="${y(tick)}" x2="${width-right}" y2="${y(tick)}"/><text class="axis-label" x="${left-9}" y="${y(tick)+4}" text-anchor="end">${tick.toFixed(1)}</text>`),
  ].join("");
  const points = wines.slice(0, 1200).map((wine) => `<circle cx="${x(value(wine,"price_thb"))}" cy="${y(value(wine,"vivino_rating"))}" r="${2 + (value(wine,"value_score") || 0) / 38}" fill="${shopColors[wine.site] || "#a89889"}" fill-opacity=".62"><title>${esc(wine.name)} — ฿${fmtPrice(wine.price_thb)} — ${value(wine,"vivino_rating").toFixed(1)}</title></circle>`).join("");
  return wines.length ? `<svg class="scatter" viewBox="0 0 ${width} ${height}" role="img" aria-label="Price versus Vivino rating scatter chart">${grid}${points}<text class="axis-label" x="${width/2}" y="${height-1}" text-anchor="middle">Price — THB, logarithmic scale</text></svg>` : '<div class="empty">No rated wines in this filter.</div>';
}

function detailBadges(wine) {
  return [wine.wine_type, wine.country, wine.region, wine.vintage, wine.size_ml ? `${wine.size_ml} ml` : null, wine.body, wine.alcohol]
    .filter((item) => item != null && item !== "").map((item) => `<span class="badge">${esc(item)}</span>`).join("");
}

function scoreBar(label, color, normalized, weight) {
  const score = (normalized || 0) * weight;
  return `<div class="score-bar"><div><span>${esc(label)}</span><span>${score.toFixed(0)} / ${weight}</span></div><div><i style="width:${(normalized || 0) * 100}%;background:${color}"></i></div></div>`;
}

function showDetail(id) {
  const wine = state.byId.get(id);
  if (!wine) return;
  const image = proxiedImage(wine.image, 420);
  const meta = [wine.producer, wine.region, wine.country].filter(Boolean).join(" · ");
  const notes = [["Appearance", wine.appearance], ["Nose", wine.nose], ["Palate", wine.palate], ["Pairing", wine.pairing]]
    .filter(([, text]) => text).map(([label, text]) => `<div class="tasting-note"><strong>${label}</strong><span>${esc(text)}</span></div>`).join("");
  const peers = wine.match_group == null ? [] : [...(state.groups.get(String(wine.match_group)) || [])].sort((a, b) => (value(a,"price_thb") || Infinity) - (value(b,"price_thb") || Infinity));
  const comparisons = peers.length > 1 ? peers.map((peer) => {
    const url = safeUrl(peer.url);
    const label = url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(peer.site)}</a>` : esc(peer.site);
    return `<div class="comparison ${peer.isCheapest ? "best" : ""}"><span>${label}${peer.isCheapest ? ' <span class="badge">Cheapest</span>' : ""}</span><strong>฿${fmtPrice(peer.price_thb)}</strong></div>`;
  }).join("") : "";
  const shopUrl = safeUrl(wine.url);
  $("#dialogBody").innerHTML = `<div class="detail">
    <div class="detail-top">${image ? `<img class="detail-img" src="${esc(image)}" alt="">` : imageMarkup(wine, "detail-img")}<div><div class="badges">${detailBadges(wine)}</div><h2>${esc(wine.name)}</h2><div class="detail-sub">${esc(meta)}</div><div class="price-rating"><span class="price"><small>฿</small>${fmtPrice(wine.price_thb)}</span>${ratingMarkup(wine)}</div></div></div>
    ${wine.description ? `<p class="detail-description">${esc(wine.description)}</p>` : ""}
    <div class="score-ledger"><div class="score-number">${(value(wine,"value_score") || 0).toFixed(0)}<small>VALUE</small></div><div>${scoreBar("Quality", "#c8a24c", value(wine,"quality"), 45)}${scoreBar("Price efficiency", "#b23047", value(wine,"price_efficiency"), 35)}${scoreBar("Cross-shop discount", "#7fa0b4", value(wine,"cross_site_gap"), 20)}</div></div>
    <section class="detail-section"><h3>Tasting profile</h3>${notes || '<div class="empty">No tasting notes published for this bottle.</div>'}</section>
    ${comparisons ? `<section class="detail-section"><h3>Same wine, other shops</h3>${comparisons}</section>` : ""}
    ${shopUrl ? `<div class="detail-actions"><a class="link-button" href="${esc(shopUrl)}" target="_blank" rel="noopener noreferrer">View at ${esc(wine.site)}</a></div>` : ""}
  </div>`;
  $("#detailDialog").showModal();
}

function setTab(tab) {
  state.tab = tab;
  $$(".tabs button").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  ["top", "browse", "insights"].forEach((name) => $(`#${name}Panel`).classList.toggle("hidden", name !== tab));
}

function scrollPanelTop() {
  $(".tabs").scrollIntoView({ behavior: "smooth", block: "start" });
}

function exportCsv() {
  const columns = ["name", "wine_type", "site", "vintage", "size_ml", "price_thb", "vivino_rating", "country", "region", "grape", "value_score", "quality", "price_efficiency", "cross_site_gap", "url"];
  const cell = (item) => `"${String(item ?? "").replace(/"/g, '""')}"`;
  const csv = [columns.join(","), ...state.filtered.map((wine) => columns.map((column) => cell(wine[column])).join(","))].join("\r\n");
  const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = Object.assign(document.createElement("a"), { href: url, download: "thai_wine_value.csv" });
  anchor.click();
  URL.revokeObjectURL(url);
}

async function init() {
  try {
    const response = await fetch("/data/wines.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`Catalog request failed with ${response.status}`);
    const payload = await response.json();
    state.wines = payload.wines || [];
    initDerivedData();
    setupControls();
    const latest = payload.latest_scrape ? new Date(payload.latest_scrape) : null;
    const dateLabel = latest && !Number.isNaN(latest.valueOf()) ? latest.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "unknown";
    $("#catalogMeta").textContent = `${fmtNumber.format(state.wines.length)} bottles · ${payload.sources || 0} shops · updated ${dateLabel}`;
    $("#loadingState").classList.add("hidden");
    applyFilters();
  } catch (error) {
    $("#loadingState").classList.add("hidden");
    $("#errorState").textContent = `Catalog could not load — ${error.message}`;
    $("#errorState").classList.remove("hidden");
  }
}

init();
