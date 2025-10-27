# -*- coding: utf-8 -*-
from __future__ import annotations

import io, os, calendar
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# NOTE: rimosse import inutilizzate per la sezione ANNO
from modules.ui_header import render_header_bar  # , render_year_bar, render_year_nav
from modules.data_loader import load_config, normalize_wide_excel
from modules.metrics import month_overview, next_6_months, filter_by_properties

# -----------------------------------------------------------------------------
# STILI BASE (unica definizione)
# -----------------------------------------------------------------------------
def inject_base_styles():
    st.markdown("""
<style>
:root{
    --dl-font: ui-sans-serif, -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    --dl-muted:#6b7280; --dl-fg:#0f172a; --dl-accent:#1f6feb; --dl-bg:#ffffff;
    --dl-ring:rgba(31,111,235,.25); --dl-radius:10px; --dl-pad:10px 12px; --dl-gap:8px;
    --dl-chip-bg:#f8fafc; --dl-chip-fg:#0f172a;
}
.dl-root, .dl-root *{ font-family: var(--dl-font); letter-spacing: .2px; }
.dl-strip{
    display:flex; align-items:center; gap: var(--dl-gap);
    background: var(--dl-bg); border:1px solid #e5e7eb; border-radius: var(--dl-radius);
    padding: 8px 10px; margin: 6px 0;
}
.dl-title{
    font-weight:600; color:var(--dl-fg); white-space:nowrap;
    padding-right:8px; border-right:1px solid #e5e7eb;
}
.dl-actions{ display:flex; gap:6px; flex-wrap:wrap; }

div.stButton>button{
    padding: var(--dl-pad);
    border-radius: 8px; border:1px solid #cbd5e1;
    background:#fff !important; color: var(--dl-fg) !important; font-weight: 600;
    transition: border-color .12s ease, box-shadow .12s ease;
    white-space: nowrap; min-width: 96px;      /* ← niente testo spezzato */
}
div.stButton>button:hover{ border-color: var(--dl-accent); box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:focus{ outline:none; box-shadow:0 0 0 3px var(--dl-ring); }

/* chip attivo/disabilitato */
div.stButton > button:disabled{
    background: var(--dl-chip-bg) !important; color: var(--dl-chip-fg) !important;
    border-color: #cbd5e1 !important; font-weight: 700 !important;
    cursor: default !important; opacity: 1 !important; box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE CONFIG + TITLE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="collapsed")
inject_base_styles()
st.markdown('<div class="dl-root"></div>', unsafe_allow_html=True)
st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# -----------------------------------------------------------------------------
# CONFIG & STATE
# -----------------------------------------------------------------------------
CFG = load_config("config.yaml")
CURRENCY = CFG.get("currency_symbol", "€")
ROOMS_DEFAULT = int(CFG.get("rooms_default", 5))
ROOMS_MAP: dict = CFG.get("rooms_per_property", {})

today = datetime.now()
st.session_state.setdefault("active_year", today.year)
st.session_state.setdefault("active_month", today.month)
st.session_state.setdefault("datasets", {})

PROPERTIES = ["Lavagnini My Place", "La Terrazza di Jenny"]
YEARS = [2024, 2025]

# -----------------------------------------------------------------------------
# SIDEBAR: Selettori + Uploader
# -----------------------------------------------------------------------------
st.sidebar.header("Carica i dati")
prop_sel = st.sidebar.selectbox("Struttura", options=PROPERTIES, index=0)
year_sel = st.sidebar.selectbox("Anno", options=YEARS, index=YEARS.index(today.year) if today.year in YEARS else 0)

upl = st.sidebar.file_uploader(
    f"File {prop_sel} – {year_sel}", type=["xlsx"], key=f"uploader_{prop_sel}_{year_sel}"
)
col_sb_a, col_sb_b = st.sidebar.columns(2)
with col_sb_a:
    if st.button("Carica file selezionato", use_container_width=True):
        if upl is None:
            st.sidebar.warning("Seleziona un file prima di caricare.")
        else:
            data = upl.read()
            df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
            df = df[df["year"] == year_sel].copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = df
            st.sidebar.success(f"Caricato: {prop_sel} – {year_sel} ({len(df)} righe)")
with col_sb_b:
    SHOW_DEMO = True
    if SHOW_DEMO and st.button("Usa file demo", use_container_width=True):
        demo_map = {
            ("Lavagnini My Place", 2024): "/mnt/data/Lavagnini_Forecast_01012024_31122024.xlsx",
            ("Lavagnini My Place", 2025): "/mnt/data/Lavagnini_Forecast_01012025_31122025.xlsx",
            ("La Terrazza di Jenny", 2024): "/mnt/data/La_Terrazza_Forecast_01092024_31122024.xlsx",
            ("La Terrazza di Jenny", 2025): "/mnt/data/La_Terrazza_Forecast_01012025_31122025.xlsx",
        }
        path = demo_map.get((prop_sel, year_sel))
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                df = normalize_wide_excel(io.BytesIO(f.read()), CFG, prop_sel)
            df = df[df["year"] == year_sel].copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = df
            st.sidebar.success(f"Demo caricata: {prop_sel} – {year_sel} ({len(df)} righe)")
        else:
            st.sidebar.warning("Demo non disponibile per la combinazione scelta.")

st.sidebar.markdown("---")
if st.sidebar.button("Svuota caricamenti"):
    st.session_state["datasets"].clear()
    st.sidebar.info("Archivio file svuotato.")

# -----------------------------------------------------------------------------
# ASSEMBLA DF GLOBALE
# -----------------------------------------------------------------------------
if not st.session_state["datasets"]:
    st.warning("Carica almeno un file (Struttura + Anno).")
    st.stop()

df_all = pd.concat(st.session_state["datasets"].values(), ignore_index=True)
properties = sorted(df_all["property"].dropna().unique().tolist())

st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Vista", options=["Singola struttura", "Aggregata"], index=0)
if view_mode == "Singola struttura":
    prop_view = st.sidebar.selectbox("Seleziona struttura per l'analisi", options=properties, index=0)
    props_to_use = [prop_view]
else:
    props_to_use = st.sidebar.multiselect("Seleziona strutture da aggregare", options=properties, default=properties)

df_view = df_all[df_all["property"].isin(props_to_use)].copy()
if df_view.empty:
    st.warning("Nessun dato per la selezione corrente."); st.stop()

# -----------------------------------------------------------------------------
# NAV UTILS MESE
# -----------------------------------------------------------------------------
def _month_labels(y: int, m: int):
    it = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    curr = f"{it[m-1]} {y}"
    pm, py = (12, y-1) if m == 1 else (m-1, y)
    nm, ny = (1, y+1) if m == 12 else (m+1, y)
    return curr, f"{it[pm-1]} {py}", f"{it[nm-1]} {ny}"

def go_prev():  # mese--
    m = st.session_state["active_month"]; y = st.session_state["active_year"]
    if m == 1: st.session_state["active_month"], st.session_state["active_year"] = 12, y-1
    else:      st.session_state["active_month"] = m-1

def go_next():  # mese++
    m = st.session_state["active_month"]; y = st.session_state["active_year"]
    if m == 12: st.session_state["active_month"], st.session_state["active_year"] = 1, y+1
    else:       st.session_state["active_month"] = m+1

active_y = st.session_state["active_year"]
active_m = st.session_state["active_month"]
curr_label, prev_label, next_label = _month_labels(active_y, active_m)

# -----------------------------------------------------------------------------
# KPI MESE per header (solo formattazioni minime per coerenza)
# -----------------------------------------------------------------------------
def _fmt_eur(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY} {s}"
def _fmt_pct(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"
def _fmt_th(n: int) -> str:
    return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

df_cur = df_view[(df_view["year"] == active_y) & (df_view["month"] == active_m)].copy()
df_prev = df_view[(df_view["year"] == active_y - 1) & (df_view["month"] == active_m)].copy()
sold_nights = int(df_cur.get("occupied", pd.Series(dtype=float)).sum()) if not df_cur.empty else 0
rooms_avail = float(df_cur.get("rooms_available", pd.Series(dtype=float)).sum()) if not df_cur.empty else 0.0
revenue     = float(df_cur.get("revenue", pd.Series(dtype=float)).sum()) if not df_cur.empty else 0.0
occ_pct     = (sold_nights / rooms_avail * 100.0) if rooms_avail > 0 else 0.0
adr         = float(df_cur.get("adr", pd.Series(dtype=float)).mean()) if not df_cur.empty else 0.0
revpar      = float(df_cur.get("revpar", pd.Series(dtype=float)).mean()) if not df_cur.empty else 0.0
sold_nights_py = int(df_prev.get("occupied", pd.Series(dtype=float)).sum()) if not df_prev.empty else 0
rooms_avail_py = float(df_prev.get("rooms_available", pd.Series(dtype=float)).sum()) if not df_prev.empty else 0.0
revenue_py     = float(df_prev.get("revenue", pd.Series(dtype=float)).sum()) if not df_prev.empty else 0.0
occ_pct_py     = (sold_nights_py / rooms_avail_py * 100.0) if rooms_avail_py > 0 else 0.0
adr_py         = float(df_prev.get("adr", pd.Series(dtype=float)).mean()) if not df_prev.empty else 0.0
revpar_py      = float(df_prev.get("revpar", pd.Series(dtype=float)).mean()) if not df_prev.empty else 0.0

kpi_header = {
    "Revenue": _fmt_eur(revenue),
    "Occupazione": _fmt_pct(occ_pct),
    "Notti vendute": _fmt_th(sold_nights),
    "ADR": _fmt_eur(adr),
    "RevPAR": _fmt_eur(revpar),
}
deltas_header = {
    "Revenue": revenue - revenue_py,
    "Occupazione": occ_pct - occ_pct_py,
    "Notti vendute": sold_nights - sold_nights_py,
    "ADR": adr - adr_py,
    "RevPAR": revpar - revpar_py,
}

# -----------------------------------------------------------------------------
# STRISCIA MESE (rimane invariata)
# -----------------------------------------------------------------------------
st.markdown('<div class="dl-strip">', unsafe_allow_html=True)
cM1, cM2 = st.columns([1, 5])
with cM1:
    st.markdown('<span class="dl-title">MESE</span>', unsafe_allow_html=True)
with cM2:
    st.markdown('<div class="dl-actions">', unsafe_allow_html=True)
    res = render_header_bar(
        month_label=curr_label,
        prev_month_label=prev_label,
        next_month_label=next_label,
        kpi=kpi_header, deltas=deltas_header,
        key_prefix="hdr_main",
        show_kpis=False,               # solo pulsanti + label
    )
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

if res.get("prev_clicked"): go_prev(); st.rerun()
if res.get("next_clicked"): go_next(); st.rerun()

# -----------------------------------------------------------------------------
# (segue tutto il resto della pagina: KPI mensili, tabelle, grafici...)
# -----------------------------------------------------------------------------
