"""Thai Wine Value Finder — "Cellar Index" dashboard.

Run:  streamlit run dashboard.py   (refresh data: python scrape.py)
Features: value scoring, tasting cards, cross-shop prices, and a personal cellar tracker.
"""
from __future__ import annotations

import html
import math
import os
from datetime import date
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st

import store
from sources import SOURCES
from enrich.cellar import drink_window, current_price_lookup

st.set_page_config(page_title="Thai Wine Value Finder", page_icon="🍷",
                   layout="wide", initial_sidebar_state="collapsed")

LABELS = {k: v["label"] for k, v in SOURCES.items()}
INK, CASK, CASK2 = "#14100E", "#1E1714", "#1A1411"
LINE, LINE2 = "#2A211C", "#3A2D26"
CHALK, CHALK2, MUTED, MUTED2 = "#F2EAE0", "#D8CCBE", "#A89889", "#6F6358"
CLARET, BRASS, SLATE = "#B23047", "#C8A24C", "#7FA0B4"
TYPE_DOT = {"Red": CLARET, "White": "#D8C27A", "Rosé": "#E0828F", "Sparkling": BRASS,
            "Champagne": BRASS, "Dessert": "#C98A3A", "Fortified": "#8A4B3A",
            "Orange": "#C97A33", "Other": MUTED2}
SITE_COLORS = {"Spirit House": CLARET, "Wine Store Asia": SLATE, "Wine Plus": BRASS,
               "Wishbeer": "#9C6B74", "Wine Duty Free": "#8A7C70"}
NOTE_COLORS = {"appearance": BRASS, "nose": CLARET, "palate": SLATE, "pairing": MUTED}
PAGE_SIZE = 15
PUBLIC_MODE = os.environ.get("WINEVALUE_PUBLIC_MODE", "").lower() in {
    "1", "true", "yes", "on",
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
.stApp{ background:#14100E;
  background-image:radial-gradient(1200px 600px at 80% -10%, rgba(178,48,71,.10), transparent 60%); }
header[data-testid="stHeader"]{ background:transparent; }
#MainMenu, footer, [data-testid="stAppDeployButton"], [data-testid="stToolbar"]{ display:none; }
html, body, [class*="css"]{ font-family:'Inter',sans-serif; color:#F2EAE0; }
h1,h2,h3,h4{ font-family:'Spectral',serif; letter-spacing:-.01em; color:#F2EAE0; }
.block-container{ max-width:1340px; padding-top:1.4rem; padding-bottom:3rem; }

.mast{ display:flex; align-items:center; gap:14px; margin-bottom:4px; }
.mast .seal{ position:relative; width:40px; height:40px; flex:none; }
.mast .seal>div{ position:absolute; inset:0; border-radius:50%;
  background:conic-gradient(from 225deg, #C8A24C 0deg 97deg, #B23047 121deg 198deg,
    #7FA0B4 216deg 251deg, rgba(255,255,255,.05) 270deg 360deg);
  -webkit-mask:radial-gradient(circle, transparent 52%, #000 53%);
  mask:radial-gradient(circle, transparent 52%, #000 53%); }
.mast .logo{ font-family:'Spectral',serif; font-weight:600; font-size:1.9rem; line-height:1; }
.mast .logo .v{ color:#B23047; font-style:italic; }
.mast .tag{ margin-left:auto; font:500 11px 'Inter'; letter-spacing:.04em; color:#A89889; }
.subtag{ color:#A89889; font:italic 400 15px/1.5 'Spectral',serif; margin:.3rem 0 1.1rem; }

[data-testid="stMetric"]{ background:#1E1714; border:1px solid #2A211C; border-radius:12px; padding:.7rem 1rem; }
[data-testid="stMetricLabel"]{ color:#6F6358; font-size:.72rem; text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetricValue"]{ font-family:'IBM Plex Mono',monospace; font-size:1.5rem; color:#F2EAE0; }

[data-testid="stExpander"]{ border:1px solid #2A211C; border-radius:12px; background:#1A1411; }
[data-testid="stExpander"] summary{ font-weight:600; color:#D8CCBE; }
.flabel{ font:600 10px 'Inter'; letter-spacing:.14em; text-transform:uppercase; color:#6F6358; margin:.2rem 0 .3rem; }

[data-testid="stPills"] button{ border-radius:20px !important; border:1px solid #3A2D26 !important;
  background:transparent !important; color:#A89889 !important; font-weight:600 !important; }
[data-testid="stPills"] button:hover{ border-color:#B23047 !important; color:#F2EAE0 !important; }
[data-testid="stPills"] button[aria-checked="true"], [data-testid="stPills"] button[aria-selected="true"]{
  background:#B23047 !important; border-color:#B23047 !important; color:#F2EAE0 !important; }

.stTabs [data-baseweb="tab-list"]{ gap:.3rem; border-bottom:1px solid #2A211C; }
.stTabs [data-baseweb="tab"]{ font-weight:600; color:#A89889; }
.stTabs [aria-selected="true"]{ color:#C8A24C !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:#C8A24C; height:2px; }

/* generic buttons */
.stButton>button{ border-radius:20px; border:1px solid #3A2D26; background:transparent;
  color:#D8CCBE; font-weight:600; }
.stButton>button:hover{ border-color:#B23047; color:#F2EAE0; }
[data-testid="stLinkButton"] a{ border-radius:20px !important; background:#B23047 !important;
  border:1px solid #B23047 !important; color:#F2EAE0 !important; font-weight:600 !important; }
[data-testid="stLinkButton"] a:hover{ background:#C5354E !important; }

/* pick cards (keyed containers) */
[class*="st-key-pk"]{ background:#1E1714; border:1px solid #2A211C; border-radius:12px;
  padding:15px 15px 12px; transition:border-color .15s; }
[class*="st-key-pk"]:hover{ border-color:#4A3A30; }
.cardhead{ display:flex; gap:12px; align-items:flex-start; }
.cardimg{ height:78px; width:54px; flex:none; object-fit:contain; background:#F2EAE0;
  border-radius:6px; padding:3px; }
.cardimg.ph{ display:flex; align-items:center; justify-content:center; font:600 22px 'Spectral',serif;
  background:#231B17; color:#6F6358; }
.eyebrow{ font:500 11px 'Inter'; color:#A89889; }
.nm{ font:600 17px/1.18 'Spectral',serif; margin-top:2px; }
.nm a{ color:#F2EAE0; text-decoration:none; } .nm a:hover{ color:#C8A24C; }
.priceM{ font:600 23px 'IBM Plex Mono',monospace; color:#F2EAE0; }
.priceM .cur{ font-size:.62em; color:#A89889; }
.stars .on{ color:#C8A24C; letter-spacing:1px; } .stars .off{ color:#3A2D26; letter-spacing:1px; }
.stars .num{ font:500 12px 'IBM Plex Mono'; color:#A89889; margin-left:.35rem; }
.unrated{ color:#6F6358; font:400 12px 'Inter'; }
.why{ font:500 12px 'Inter'; color:#C8A24C; }

.badge{ display:inline-block; font:600 10.5px 'Inter'; padding:.18rem .55rem; border-radius:6px;
  border:1px solid #3A2D26; color:#A89889; margin:0 .28rem .3rem 0; background:#181210; white-space:nowrap; }
.badge.type{ border-color:#B23047; color:#E0828F; }
.badge.deal{ border-color:#7FA0B4; color:#7FA0B4; }
.badge.drunk{ border-color:#6F6358; color:#8A7C70; }

/* browse rows */
.bhead{ display:grid; grid-template-columns:1fr 110px 110px 70px; gap:10px; padding:0 4px 8px;
  border-bottom:1px solid #2A211C; font:600 10px 'Inter'; letter-spacing:.12em;
  text-transform:uppercase; color:#6F6358; }
.brow{ display:grid; grid-template-columns:1fr 110px 110px 70px; gap:10px; align-items:center; }
.brow .bn{ font:600 14px/1.15 'Spectral',serif; color:#F2EAE0; }
.brow .bm{ font:400 11px 'Inter'; color:#8A7C70; margin-top:1px; }
.brow .bt{ font:500 12px 'Inter'; color:#D8CCBE; }
.brow .dot{ display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.brow .bp{ font:600 13px 'IBM Plex Mono'; color:#D8CCBE; }
.brow .bv{ font:600 15px 'IBM Plex Mono'; color:#C8A24C; }

/* detail / dialog */
.detail{ background:#1E1714; border:1px solid #2A211C; border-radius:14px; padding:20px 22px; }
.detail h2{ margin:.1rem 0 .25rem; font:600 24px 'Spectral',serif; }
.detail .prod{ color:#A89889; font:400 13px 'Inter'; margin-bottom:.6rem; }
.detail .blurb{ font:italic 400 14px/1.55 'Spectral',serif; color:#D8CCBE; margin:.5rem 0 .2rem; }
.dimg{ display:block; margin:0 auto .6rem; max-height:150px; width:auto; background:#F2EAE0;
  border-radius:8px; padding:6px; }
.sealcard{ background:#181210; border:1px solid #2A211C; border-radius:12px; padding:16px 18px;
  margin:.9rem 0; display:flex; align-items:center; gap:22px; flex-wrap:wrap; }
.breakdown{ flex:1; min-width:200px; display:flex; flex-direction:column; gap:12px; }
.brk .top{ display:flex; justify-content:space-between; font:600 12px 'Inter'; color:#E6DBCE; }
.brk .d{ display:inline-block; width:8px; height:8px; border-radius:2px; margin-right:7px; }
.brk .pts{ font:500 11px 'IBM Plex Mono'; color:#A89889; }
.brk .track{ height:5px; background:#2A211C; border-radius:3px; margin-top:6px; overflow:hidden; }
.brk .fill{ height:100%; border-radius:3px; }
.sec-label{ font:600 11px 'Inter'; letter-spacing:.14em; text-transform:uppercase; color:#6F6358; margin:1rem 0 .7rem; }
.tnote{ display:grid; grid-template-columns:84px 1fr; gap:14px; align-items:start; padding-left:14px; margin-bottom:13px; }
.tnote .lab{ font:600 11px 'Inter'; letter-spacing:.06em; text-transform:uppercase; padding-top:1px; }
.tnote .txt{ font:400 13.5px/1.55 'Spectral',serif; color:#D8CCBE; }
.cmprow{ display:flex; justify-content:space-between; align-items:center; padding:.45rem .6rem;
  border-radius:8px; border:1px solid #2A211C; margin-bottom:6px; }
.cmprow.best{ background:rgba(178,48,71,.12); box-shadow:inset 3px 0 0 #B23047; }
.cmprow .shop{ font:500 13px 'Inter'; color:#E6DBCE; }
.cmprow .tagcheap{ font:600 9.5px 'Inter'; letter-spacing:.06em; text-transform:uppercase;
  color:#1C1A19; background:#C8A24C; border-radius:4px; padding:2px 7px; margin-left:8px; }
.cmprow .pr{ font:600 14px 'IBM Plex Mono'; }
.empty-panel{ background:#181210; border:1px dashed #3A2D26; border-radius:10px; padding:16px 18px;
  font:italic 400 13px 'Spectral',serif; color:#8A7C70; }
.owned{ background:rgba(200,162,76,.10); border:1px solid #4A3A30; border-radius:10px;
  padding:10px 14px; margin:.4rem 0; font:500 13px 'Inter'; color:#D8CCBE; }

/* cellar */
[class*="st-key-cellar"]{ background:#1E1714; border:1px solid #2A211C; border-radius:12px; padding:14px 16px; }
.cellname{ font:600 16px 'Spectral',serif; } .cellmeta{ font:400 12px 'Inter'; color:#8A7C70; }
hr{ border-color:#2A211C; }
[data-testid="stDataFrame"]{ border:1px solid #2A211C; border-radius:10px; }
</style>
"""


# --------------------------------------------------------------------- data
@st.cache_data(show_spinner=False)
def load_data(db_path, _mtime):
    df = pd.DataFrame(store.read_wines(db_path))
    if df.empty:
        return df
    df["site"] = df["source"].map(LABELS).fillna(df["source"])
    df["critic_best"] = df["critic_scores"].apply(
        lambda s: max((d.get("score", 0) for d in s), default=None) if s else None)
    df["listings"] = df.groupby("match_group")["source"].transform("count")
    df["cheapest_in_group"] = df.groupby("match_group")["price_thb"].transform("min")
    df["is_cheapest"] = df["cheapest_in_group"].eq(df["price_thb"]) & (df["listings"] > 1)
    for c in ("quality", "price_efficiency", "cross_site_gap", "value_score",
              "vivino_rating", "price_thb", "vintage"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["has_tasting"] = df[["nose", "palate", "appearance"]].apply(
        lambda r: any(str(x).strip() not in ("", "None", "nan") for x in r), axis=1)
    return df


def _mtime(p):
    return os.path.getmtime(p) if os.path.exists(p) else 0.0


# --------------------------------------------------------------------- helpers
def esc(x):
    return html.escape(str(x)) if x is not None and str(x) not in ("nan", "None") else ""


def has(x):
    return x is not None and str(x).strip() not in ("", "nan", "None")


def fmt_price(p):
    return f"{p:,.0f}" if pd.notna(p) and p is not None else "—"


def stars_html(rating):
    if not pd.notna(rating) or not rating:
        return '<span class="unrated">Unrated</span>'
    n = int(round(rating))
    return (f'<span class="stars"><span class="on">{"★"*n}</span>'
            f'<span class="off">{"☆"*(5-n)}</span><span class="num">{rating:.1f}</span></span>')


def value_seal(score, q, pe, disc, size=190):
    q, pe, disc = q or 0, pe or 0, disc or 0
    qF, pF, dF = 121.5 * q, 121.5 + 94.5 * pe, 216 + 54 * disc
    conic = (f"conic-gradient(from 225deg,"
             f"#C8A24C 0deg {qF:.1f}deg, rgba(200,162,76,.16) {qF:.1f}deg 121.5deg,"
             f"#B23047 121.5deg {pF:.1f}deg, rgba(178,48,71,.16) {pF:.1f}deg 216deg,"
             f"#7FA0B4 216deg {dF:.1f}deg, rgba(127,160,180,.16) {dF:.1f}deg 270deg,"
             f"rgba(255,255,255,.045) 270deg 360deg)")
    mask = "radial-gradient(circle, transparent 55%, #000 56%)"
    return (
        f'<div style="position:relative;width:{size}px;height:{size}px;flex:none">'
        '<div style="position:absolute;inset:-22px;border-radius:50%;'
        'background:radial-gradient(circle, rgba(178,48,71,.30), transparent 68%)"></div>'
        f'<div style="position:absolute;inset:0;border-radius:50%;background:{conic};'
        f'-webkit-mask:{mask};mask:{mask}"></div>'
        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;'
        'align-items:center;justify-content:center">'
        '<div style="font:500 10px Inter;letter-spacing:.26em;text-transform:uppercase;color:#C8A24C">Value</div>'
        f'<div style="font:600 {size*0.32:.0f}px/1 Spectral,serif;color:#F2EAE0">{score:.0f}</div>'
        '<div style="font:400 11px \'IBM Plex Mono\';color:#6F6358">/ 100</div></div></div>')


def value_ledger(score, q, pe, disc):
    q, pe, disc = q or 0, pe or 0, disc or 0
    return (
        '<div style="margin-top:2px"><div style="display:flex;align-items:baseline;gap:9px;margin-bottom:8px">'
        f'<span style="font:600 32px/1 Spectral,serif;color:#F2EAE0">{score:.0f}</span>'
        '<span style="font:500 9px Inter;letter-spacing:.2em;text-transform:uppercase;color:#C8A24C">Value</span></div>'
        '<div style="display:flex;gap:4px;height:7px;border-radius:4px;overflow:hidden;background:#2A211C">'
        f'<div style="width:{q*45:.1f}%;background:#C8A24C"></div>'
        f'<div style="width:{pe*35:.1f}%;background:#B23047"></div>'
        f'<div style="width:{disc*20:.1f}%;background:#7FA0B4"></div></div></div>')


def proxied(url, w=240):
    """Route shop images through the free wsrv.nl proxy — bypasses hot-link blocks
    (so images load when the site is served from a different domain) and resizes."""
    if not url:
        return ""
    return "https://wsrv.nl/?url=" + quote(str(url), safe="") + f"&w={w}&output=webp&q=82"


def img_html(row, cls="cardimg"):
    if has(row.get("image")):
        return (f'<img class="{cls}" src="{esc(proxied(row["image"], 160))}" '
                f'referrerpolicy="no-referrer" loading="lazy" '
                f'onerror="this.style.visibility=\'hidden\'">')
    initial = esc((row.get("wine_type") or "?")[:1])
    return f'<div class="{cls} ph">{initial}</div>'


def badges(row):
    out = []
    if has(row.get("wine_type")):
        out.append(f'<span class="badge type">{esc(row["wine_type"])}</span>')
    for fld in ("country", "region"):
        if has(row.get(fld)):
            out.append(f'<span class="badge">{esc(row[fld])}</span>')
    if pd.notna(row.get("vintage")):
        out.append(f'<span class="badge">{int(row["vintage"])}</span>')
    if has(row.get("size_ml")):
        out.append(f'<span class="badge">{int(row["size_ml"])}ml</span>')
    if has(row.get("body")):
        out.append(f'<span class="badge">{esc(row["body"])}</span>')
    if has(row.get("alcohol")):
        out.append(f'<span class="badge">{esc(row["alcohol"])}</span>')
    if row.get("is_cheapest"):
        out.append(f'<span class="badge deal">Cheapest of {int(row["listings"])}</span>')
    return "".join(out)


def why(row):
    if row.get("is_cheapest"):
        return f"Cheapest of {int(row['listings'])} listings"
    if (row.get("quality") or 0) >= 0.86:
        return "Top rated"
    if (row.get("price_efficiency") or 0) >= 0.8:
        return "Great quality for the price"
    if (row.get("cross_site_gap") or 0) >= 0.2:
        return "Below the cross-shop median"
    return "Solid everyday value"


def card_visual(row):
    nm = esc(row["name"])
    link = f'<a href="{esc(row["url"])}" target="_blank">{nm}</a>' if has(row.get("url")) else nm
    eb = " · ".join(filter(None, [esc(row.get("wine_type")), esc(row.get("country")),
                    str(int(row["vintage"])) if pd.notna(row.get("vintage")) else ""]))
    return (
        f'<div class="cardhead">{img_html(row)}'
        f'<div><div class="eyebrow">{eb}</div><div class="nm">{link}</div></div></div>'
        '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:10px">'
        f'<span class="priceM"><span class="cur">฿</span>{fmt_price(row["price_thb"])}</span>'
        f'{stars_html(row.get("vivino_rating"))}</div>'
        '<div style="border-top:1px solid #2A211C;margin-top:11px;padding-top:11px">'
        f'{value_ledger(row["value_score"], row.get("quality"), row.get("price_efficiency"), row.get("cross_site_gap"))}</div>'
        f'<div class="why" style="margin-top:9px">✦ {esc(why(row))}</div>')


def _bar(label, color, pts, cap, pct):
    return (f'<div class="brk"><div class="top"><span><span class="d" style="background:{color}"></span>{label}</span>'
            f'<span class="pts">{pts:.0f} / {cap}</span></div>'
            f'<div class="track"><div class="fill" style="width:{min(100,pct):.0f}%;background:{color}"></div></div></div>')


def detail_html(row, full_df):
    nm = esc(row["name"])
    prod = " · ".join(filter(None, [esc(row.get("producer")), esc(row.get("region")), esc(row.get("country"))]))
    prod_html = f'<div class="prod">{prod}</div>' if prod else ""
    blurb = f'<div class="blurb">{esc(row["description"])}</div>' if has(row.get("description")) else ""
    img = (f'<img class="dimg" src="{esc(proxied(row["image"], 420))}" referrerpolicy="no-referrer" '
           f'onerror="this.style.display=\'none\'">') if has(row.get("image")) else ""

    q, pe, disc = row.get("quality") or 0, row.get("price_efficiency") or 0, row.get("cross_site_gap") or 0
    seal = value_seal(row.get("value_score") or 0, q, pe, disc, size=170)
    bars = (_bar("Quality", BRASS, q*45, 45, q*100) + _bar("Price efficiency", CLARET, pe*35, 35, pe*100)
            + _bar("Cross-shop discount", SLATE, disc*20, 20, disc*100))
    sealcard = f'<div class="sealcard">{seal}<div class="breakdown">{bars}</div></div>'

    notes = []
    for label, field in [("Appearance", "appearance"), ("Nose", "nose"), ("Palate", "palate"), ("Pairing", "pairing")]:
        if has(row.get(field)):
            c = NOTE_COLORS[field]
            notes.append(f'<div class="tnote" style="border-left:2px solid {c}">'
                         f'<span class="lab" style="color:{c}">{label}</span>'
                         f'<span class="txt">{esc(row[field])}</span></div>')
    tasting = ('<div class="sec-label">Tasting profile</div>'
               + (f'<div>{"".join(notes)}</div>' if notes
                  else '<div class="empty-panel">No tasting notes published for this bottle.</div>'))

    chips = ""
    if row.get("critic_scores"):
        chips = " ".join(f'<span class="badge">{esc(d.get("critic"))} {d.get("score")}</span>'
                         for d in row["critic_scores"])

    cmp_html = ""
    grp = row.get("match_group")
    if pd.notna(grp):
        peers = full_df[full_df["match_group"] == grp].sort_values("price_thb")
        if len(peers) > 1:
            best = peers["price_thb"].min()
            rows = ""
            for _, p in peers.iterrows():
                cls = " best" if p["price_thb"] == best else ""
                shop = (f'<a href="{esc(p["url"])}" target="_blank" style="color:#E6DBCE;text-decoration:none">{esc(p["site"])}</a>'
                        if has(p.get("url")) else esc(p["site"]))
                tag = '<span class="tagcheap">Cheapest</span>' if p["price_thb"] == best else ""
                vint = f'<span style="color:#6F6358;font:400 11.5px Inter;margin-right:12px">{int(p["vintage"])}</span>' if pd.notna(p.get("vintage")) else ""
                pc = BRASS if p["price_thb"] == best else CHALK
                rows += (f'<div class="cmprow{cls}"><span class="shop">{shop}{tag}</span>'
                         f'<span>{vint}<span class="pr" style="color:{pc}">฿{fmt_price(p["price_thb"])}</span></span></div>')
            cmp_html = f'<div class="sec-label">Same wine, other shops</div>{rows}'

    dw = drink_window(int(row["vintage"]) if pd.notna(row.get("vintage")) else None,
                      row.get("wine_type"), row.get("body"))
    dw_color = {"Ready": "#7FB46A", "Hold": SLATE, "Past peak": MUTED2,
                "Ready now": BRASS}.get(dw["status"], MUTED)
    dw_html = (f'<div style="margin:.5rem 0 0;font:600 12px Inter;color:{dw_color}">'
               f'⌛ Drink window: {dw["label"]} · {dw["status"]}</div>')

    return (
        f'<div class="detail">{img}<div>{badges(row)}</div><h2>{nm}</h2>{prod_html}'
        '<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:10px">'
        f'<span class="priceM" style="font-size:1.5rem"><span class="cur">฿</span>{fmt_price(row["price_thb"])}</span>'
        f'<span>{stars_html(row.get("vivino_rating"))}{" &nbsp; " + chips if chips else ""}</span></div>'
        f'{dw_html}{blurb}{sealcard}{tasting}{cmp_html}</div>')


# --------------------------------------------------------------------- dialog
@st.dialog("Tasting card", width="large")
def tasting_dialog(wine, full_df, db):
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(detail_html(wine, full_df), unsafe_allow_html=True)
    if has(wine.get("url")):
        st.link_button(f"View at {wine['site']} ↗", wine["url"])

    if PUBLIC_MODE:
        st.caption("Cellar tracking is available in local deployments only.")
        return

    owned = [p for p in store.read_purchases(db)
             if p["source"] == wine.get("source") and p["source_id"] == str(wine.get("source_id"))]
    if owned:
        for p in owned:
            tot = (p["price_paid"] or 0) * (p["quantity"] or 1)
            st.markdown(
                f'<div class="owned">🍷 In your cellar: {p["quantity"]}× bought {p["bought_date"]} '
                f'· ฿{tot:,.0f}{" · " + esc(p["notes"]) if p["notes"] else ""}</div>',
                unsafe_allow_html=True)
            with st.form(f"rm_{p['id']}", clear_on_submit=True):
                if st.form_submit_button("Remove from cellar"):
                    store.delete_purchase(p["id"], db)
                    st.toast("Removed from cellar")
                    st.rerun()

    st.markdown("**🍷 I bought this**")
    with st.form(f"buy_{wine.get('source')}_{wine.get('source_id')}", clear_on_submit=True):
        c = st.columns(3)
        qty = c[0].number_input("Bottles", 1, 99, 1)
        default_price = float(wine["price_thb"]) if pd.notna(wine.get("price_thb")) else 0.0
        price = c[1].number_input("Price paid each (฿)", 0.0, value=default_price, step=10.0)
        bought = c[2].date_input("Date bought", value=date.today())
        notes = st.text_area("Notes (optional)", placeholder="Occasion, who with, your own rating…")
        if st.form_submit_button("＋ Add to my cellar", type="primary"):
            store.add_purchase({
                "source": wine.get("source"), "source_id": str(wine.get("source_id")),
                "name": wine.get("name"), "site": wine.get("site"),
                "price_paid": float(price), "quantity": int(qty),
                "bought_date": bought.isoformat(),
                "vintage": int(wine["vintage"]) if pd.notna(wine.get("vintage")) else None,
                "wine_type": wine.get("wine_type"), "notes": notes}, db)
            st.toast(f"Added {qty}× {wine.get('name')} to your cellar 🍷")
            st.rerun()


# ===================================================================== app
st.markdown(CSS, unsafe_allow_html=True)
SORT_OPTS = {"value_score": "Value", "quality": "Quality", "price_efficiency": "Price-eff",
             "cross_site_gap": "Discount", "price_thb": "Price"}
RATING_OPTS = {"Any": 0.0, "3.5★+": 3.5, "4.0★+": 4.0, "4.5★+": 4.5}
DB = store.DEFAULT_DB            # wine catalog (read-only here)
CELLAR_DB = store.DEFAULT_CELLAR_DB  # personal purchases (persists separately)

if not os.path.exists(DB):
    st.title("🍷 Thai Wine Value Finder")
    st.warning("No data yet. Run `python scrape.py`, then reload.")
    st.stop()

df = load_data(DB, _mtime(DB))
if df.empty:
    st.warning("The database is empty. Run `python scrape.py`.")
    st.stop()

st.markdown(
    '<div class="mast"><div class="seal"><div></div></div>'
    '<span class="logo">Thai Wine <span class="v">Value</span> Finder</span>'
    f'<span class="tag">{len(df):,} bottles · {df["site"].nunique()} shops · '
    f'updated {pd.to_datetime(df["scraped_at"]).max():%d %b %Y}</span></div>'
    f'<div class="subtag">Find the best bottle for your baht'
    f'{" — public catalog" if PUBLIC_MODE else " — and keep your cellar"}.</div>',
    unsafe_allow_html=True)

if st.button("↺ Reset filters"):
    for k in [k for k in st.session_state if k.startswith("f_")]:
        del st.session_state[k]
    st.rerun()

with st.expander("🔎 Filters & sorting", expanded=True):
    c = st.columns([2.4, 1.2, 1.2])
    pmax = int(df["price_thb"].max())
    price = c[0].slider("Price (฿)", 0, min(pmax, 50000), (0, 5000), step=100, key="f_price")
    search = c[1].text_input("Search", key="f_search", placeholder="Malbec, Penfolds, Italy…")
    sort_by = c[2].selectbox("Rank by", list(SORT_OPTS), format_func=lambda k: SORT_OPTS[k], key="f_sort")
    st.markdown('<div class="flabel">Type</div>', unsafe_allow_html=True)
    types = st.pills("Type", sorted(df["wine_type"].dropna().unique()), selection_mode="multi",
                     key="f_type", label_visibility="collapsed")
    st.markdown('<div class="flabel">Shop</div>', unsafe_allow_html=True)
    sites = st.pills("Shop", sorted(df["site"].unique()), selection_mode="multi",
                     key="f_site", label_visibility="collapsed")
    cc = st.columns([1.4, 2])
    with cc[0]:
        st.markdown('<div class="flabel">Min rating</div>', unsafe_allow_html=True)
        rating_lbl = st.pills("Min rating", list(RATING_OPTS), default="Any", key="f_rating",
                              label_visibility="collapsed")
    with cc[1]:
        st.markdown('<div class="flabel">Only show</div>', unsafe_allow_html=True)
        toggles = st.pills("Only show", ["Has rating", "Tasting notes", "Cross-shop only"],
                           selection_mode="multi", key="f_only", label_visibility="collapsed")

f = df[(df["price_thb"] >= price[0]) & (df["price_thb"] <= price[1])].copy()
if types:
    f = f[f["wine_type"].isin(types)]
if sites:
    f = f[f["site"].isin(sites)]
if RATING_OPTS.get(rating_lbl or "Any", 0.0) > 0:
    f = f[f["vivino_rating"].fillna(0) >= RATING_OPTS[rating_lbl]]
toggles = toggles or []
if "Has rating" in toggles:
    f = f[f["quality"].notna()]
if "Tasting notes" in toggles:
    f = f[f["has_tasting"]]
if "Cross-shop only" in toggles:
    f = f[f["listings"] > 1]
if search:
    s = search.lower()
    f = f[f[["name", "grape", "country", "region"]].fillna("").apply(
        lambda r: s in " ".join(r.values).lower(), axis=1)]
f = f.sort_values(sort_by, ascending=(sort_by == "price_thb"), na_position="last").reset_index(drop=True)

m = st.columns(4)
m[0].metric("Bottles shown", f"{len(f):,}")
m[1].metric("Distinct wines", f"{f['match_group'].nunique():,}" if len(f) else "0")
m[2].metric("With a rating", f"{int(f['quality'].notna().sum()):,}")
m[3].metric("Median price", f"฿{f['price_thb'].median():,.0f}" if len(f) else "–")


def _winerow(src, sid):
    mm = df[(df["source"] == src) & (df["source_id"].astype(str) == str(sid))]
    return mm.iloc[0] if len(mm) else None


def _now_price(p):
    r = _winerow(p["source"], p["source_id"])
    return float(r["price_thb"]) if r is not None and pd.notna(r["price_thb"]) else None


def _save_rating(pid):
    v = st.session_state.get(f"rate{pid}")
    if v is not None:
        store.set_purchase_rating(pid, int(v) + 1, CELLAR_DB)


cellar_n = 0 if PUBLIC_MODE else len(store.read_purchases(CELLAR_DB))
tabs = st.tabs(["🏆 Top Picks", "🔍 Browse & taste", f"🍷 My Cellar ({cellar_n})", "📊 Insights"])

# ---- Top Picks ----
with tabs[0]:
    if f.empty:
        st.markdown('<div class="empty-panel">No bottles match these filters — loosen one to start.</div>',
                    unsafe_allow_html=True)
    else:
        st.caption(f"Best {min(12, len(f))} by {SORT_OPTS[sort_by].lower()}.")
        picks = f.head(12).reset_index(drop=True)
        for i in range(0, len(picks), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j >= len(picks):
                    continue
                row = picks.iloc[i + j]
                with col.container(key=f"pk{i+j}"):
                    st.markdown(card_visual(row), unsafe_allow_html=True)
                    bcols = st.columns(2)
                    if bcols[0].button("🍷 Tasting card", key=f"tc{i+j}", width="stretch"):
                        tasting_dialog(row.to_dict(), df, CELLAR_DB)
                    if has(row.get("url")):
                        bcols[1].link_button("View ↗", row["url"], width="stretch")

# ---- Browse ----
with tabs[1]:
    if f.empty:
        st.markdown('<div class="empty-panel">No bottles match these filters — loosen one to start.</div>',
                    unsafe_allow_html=True)
    else:
        npages = max(1, math.ceil(len(f) / PAGE_SIZE))
        page = min(st.session_state.get("f_page", 1), npages)
        nav = st.columns([1, 1, 4, 1])
        if nav[0].button("‹ Prev", disabled=page <= 1):
            st.session_state["f_page"] = page - 1
            st.rerun()
        if nav[1].button("Next ›", disabled=page >= npages):
            st.session_state["f_page"] = page + 1
            st.rerun()
        lo, hi = (page - 1) * PAGE_SIZE, min(page * PAGE_SIZE, len(f))
        nav[2].caption(f"Showing {lo+1}–{hi} of {len(f):,} · page {page}/{npages}. "
                       "Click a bottle to open its tasting card.")
        st.markdown('<div class="bhead"><span>Bottle</span><span>Type</span>'
                    '<span>Price</span><span>Value</span></div>', unsafe_allow_html=True)
        for idx in range(lo, hi):
            row = f.iloc[idx]
            rc = st.columns([7.3, 1.1])
            meta = " · ".join(filter(None, [esc(row.get("country")), esc(row.get("region")),
                              str(int(row["vintage"])) if pd.notna(row.get("vintage")) else ""]))
            dot = TYPE_DOT.get(row.get("wine_type"), MUTED2)
            rc[0].markdown(
                f'<div class="brow"><div><div class="bn">{esc(row["name"])}</div>'
                f'<div class="bm">{meta}</div></div>'
                f'<div class="bt"><span class="dot" style="background:{dot}"></span>{esc(row.get("wine_type"))}</div>'
                f'<div class="bp">฿{fmt_price(row["price_thb"])}</div>'
                f'<div class="bv">{row["value_score"]:.0f}</div></div>', unsafe_allow_html=True)
            if rc[1].button("View", key=f"row{idx}", width="stretch"):
                tasting_dialog(row.to_dict(), df, CELLAR_DB)

# ---- My Cellar ----
with tabs[2]:
    purchases = [] if PUBLIC_MODE else store.read_purchases(CELLAR_DB)
    if PUBLIC_MODE:
        st.markdown('<div class="empty-panel">Cellar tracking is disabled on the public site. '
                    'Run the app locally to keep a private purchase history.</div>',
                    unsafe_allow_html=True)
    elif not purchases:
        st.markdown('<div class="empty-panel">Your cellar is empty. Open any wine\'s tasting '
                    'card and tap <b>＋ Add to my cellar</b> to start tracking what you buy.</div>',
                    unsafe_allow_html=True)
    else:
        in_cellar = [p for p in purchases if p["status"] == "cellar"]
        spent_all = sum((p["price_paid"] or 0) * (p["quantity"] or 1) for p in purchases)
        value_now = sum((_now_price(p) or 0) * (p["quantity"] or 1) for p in in_cellar)
        paid_cellar = sum((p["price_paid"] or 0) * (p["quantity"] or 1) for p in in_cellar)
        cm = st.columns(4)
        cm[0].metric("Bottles in cellar", f"{sum(p['quantity'] or 1 for p in in_cellar):,}")
        cm[1].metric("Total spent", f"฿{spent_all:,.0f}")
        cm[2].metric("Cellar value now", f"฿{value_now:,.0f}",
                     delta=f"฿{value_now - paid_cellar:,.0f} vs paid" if value_now else None)
        cm[3].metric("Bottles opened",
                     f"{sum(p['quantity'] or 1 for p in purchases if p['status']=='drunk'):,}")
        st.markdown("")
        for p in purchases:
            with st.container(key=f"cellar{p['id']}"):
                cols = st.columns([4.4, 1.5, 2, 1.6, 1.2])
                drunk = p["status"] == "drunk"
                tag = ('<span class="badge drunk">Opened</span>' if drunk
                       else '<span class="badge type">In cellar</span>')
                dw = drink_window(p.get("vintage"), p.get("wine_type"),
                                  getattr(_winerow(p["source"], p["source_id"]), "body", None))
                dwc = {"Ready": "#7FB46A", "Hold": SLATE, "Past peak": MUTED2,
                       "Ready now": BRASS}.get(dw["status"], MUTED)
                vint = f' · {p["vintage"]}' if p.get("vintage") else ""
                cols[0].markdown(
                    f'<div class="cellname">{esc(p["name"])} {tag}</div>'
                    f'<div class="cellmeta">{esc(p["site"])}{vint} · bought {p["bought_date"]}'
                    f'{" · " + esc(p["notes"]) if p["notes"] else ""}</div>'
                    f'<div style="font:600 11px Inter;color:{dwc};margin-top:3px">'
                    f'⌛ Drink {dw["label"]} · {dw["status"]}</div>', unsafe_allow_html=True)
                # your rating (stars) — saved on change
                if f"rate{p['id']}" not in st.session_state and p.get("my_rating"):
                    st.session_state[f"rate{p['id']}"] = int(round(p["my_rating"])) - 1
                cols[1].caption("Your rating")
                cols[1].feedback("stars", key=f"rate{p['id']}", on_change=_save_rating,
                                 args=(p["id"],))
                np_ = _now_price(p)
                paid_each = p["price_paid"] or 0
                if np_:
                    d = np_ - paid_each
                    nowc = "#7FB46A" if d >= 0 else "#E0828F"
                    nowline = (f'<div style="font:500 12px IBM Plex Mono;color:{nowc};margin-top:3px">'
                               f'now ฿{np_:,.0f} ({"+" if d>=0 else ""}{d:,.0f})</div>')
                else:
                    nowline = ""
                cols[2].markdown(
                    f'<div style="text-align:right"><div style="font:600 14px IBM Plex Mono;color:#F2EAE0">'
                    f'{p["quantity"]}× ฿{paid_each:,.0f}</div>'
                    f'<div style="font:400 11px Inter;color:#6F6358">฿{paid_each*(p["quantity"] or 1):,.0f} paid</div>'
                    f'{nowline}</div>', unsafe_allow_html=True)
                if cols[3].button("Move to cellar" if drunk else "Mark opened", key=f"d{p['id']}",
                                  width="stretch"):
                    store.set_purchase_status(p["id"], "cellar" if drunk else "drunk", CELLAR_DB)
                    st.rerun()
                if cols[4].button("Remove", key=f"rm{p['id']}", width="stretch"):
                    store.delete_purchase(p["id"], CELLAR_DB)
                    st.rerun()

# ---- Insights ----
with tabs[3]:
    if f.empty:
        st.markdown('<div class="empty-panel">No bottles to chart.</div>', unsafe_allow_html=True)
    else:
        def dark(fig, h=420):
            fig.update_layout(height=h, paper_bgcolor=CASK2, plot_bgcolor=CASK2, font_color=MUTED,
                              font_family="Inter", legend_title_text="", margin=dict(l=10, r=10, t=10, b=10))
            fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE)
            fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE)
            return fig
        c1, c2 = st.columns([3, 2])
        rated = f[f["vivino_rating"].notna() & f["price_thb"].notna()]
        with c1:
            st.markdown("**Price vs rating** — bottom-right is the value sweet spot")
            if len(rated):
                fig = px.scatter(rated, x="price_thb", y="vivino_rating", color="site", size="value_score",
                                 hover_name="name", log_x=True, color_discrete_map=SITE_COLORS,
                                 labels={"price_thb": "Price ฿ (log)", "vivino_rating": "Vivino ⭐"})
                st.plotly_chart(dark(fig), width="stretch")
            else:
                st.markdown('<div class="empty-panel">No rated wines in this filter to plot.</div>',
                            unsafe_allow_html=True)
        with c2:
            st.markdown("**Value by shop**")
            st.plotly_chart(dark(px.box(f, x="site", y="value_score", color="site",
                            color_discrete_map=SITE_COLORS).update_layout(showlegend=False, xaxis_title="",
                            xaxis_tickangle=-25), 200), width="stretch")
            st.markdown("**Bottles by type**")
            cnt = f["wine_type"].value_counts().reset_index()
            cnt.columns = ["type", "n"]
            st.plotly_chart(dark(px.bar(cnt, x="type", y="n", color_discrete_sequence=[CLARET])
                            .update_layout(showlegend=False, xaxis_title="", yaxis_title=""), 200), width="stretch")

st.divider()
if not f.empty:
    export_cols = ["name", "wine_type", "site", "vintage", "size_ml", "price_thb", "vivino_rating",
                   "body", "alcohol", "country", "region", "grape", "value_score", "quality",
                   "price_efficiency", "cross_site_gap", "listings", "nose", "palate", "appearance",
                   "pairing", "description", "url"]
    st.download_button("⬇️ Export this list (CSV)",
                       f[export_cols].to_csv(index=False).encode("utf-8-sig"),
                       file_name="thai_wine_value.csv", mime="text/csv")
