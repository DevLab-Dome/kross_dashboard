# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import io
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------
# Safe optional imports (do not crash if helper modules are missing)
# ---------------------------------------------------------------------
try:
    from baseline_loader import load_all_baselines, get_year_data, monthly_kpi  # type: ignore
except Exception:
    load_all_baselines = None
    get_year_data = None
    monthly_kpi = None

# ---------------------------------------------------------------------
# Styling (inserted immediately after imports, as requested)
# ---------------------------------------------------------------------
def _inject_sidebar_css() -> None:
    st.markdown("""
    <style>
    [data-testid="stSidebar"] .block-container { padding-top: 0.75rem; padding-bottom: 1rem; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-weight: 600 !important; font-size: 0.95rem !important; letter-spacing: .02em;
        padding: 8px 10px; margin: 10px -8px 8px -8px; border-radius: 6px;
        background: rgba(0,0,0,.04); border: 1px solid rgba(0,0,0,.08);
    }
    [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiSelect,
    [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stDateInput,
    [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stFileUploader,
    [data-testid="stSidebar"] button[kind="secondary"], [data-testid="stSidebar"] button[kind="primary"] {
        margin-top: 4px; margin-bottom: 10px;
    }
    [data-testid="stSidebar"] label { font-weight: 500; }
    [data-testid="stSidebar"] .stRadio > div { row-gap: 0.25rem; }
    .kpi-pill{display:inline-block;padding:.35rem .5rem;border-radius:999px;border:1px solid rgba(0,0,0,.08);margin-top:.35rem;font-size:.8rem;}
    .kpi-pill.up{ background:#ecfdf5;color:#047857;}
    .kpi-pill.down{ background:#fef2f2;color:#dc2626;}
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="expanded")
_inject_sidebar_css()

st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# ---------------------------------------------------------------------
# Data loading – baselines
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _load_baselines_cached() -> pd.DataFrame | None:
    if load_all_baselines is None:
        return None
    try:
        df = load_all_baselines()
        if df is not None and not df.empty:
            # normalize columns expected by the app
            rename_map = {
                "stay_date": "stay_date",
                "date": "stay_date",
                "rooms_sold": "rooms_sold",
                "occupied": "rooms_sold",
                "revenue_total": "revenue_total",
                "revenue": "revenue_total",
                "adr": "adr",
                "revpar": "revpar",
                "property": "property",
                "prop": "property",
            }
            df = df.rename(columns=rename_map)
            # ensure types
            df["stay_date"] = pd.to_datetime(df["stay_date"])
            for c in ["rooms_sold"]:
                if c in df: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
            for c in ["revenue_total","adr","revpar"]:
                if c in df: df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
            # add helpers
            df["year"] = df["stay_date"].dt.year
            df["month"] = df["stay_date"].dt.month
            df["property"] = df["property"].astype(str)
            return df
    except Exception as e:
        st.warning(f"Impossibile caricare i baseline: {e}")
    return None

BASELINE_ALL = _load_baselines_cached()

# ---------------------------------------------------------------------
# Sidebar – order EXACTLY as requested
# ---------------------------------------------------------------------
# (A) Section: Vista
st.sidebar.header("Vista")
props_list: List[str] = sorted(BASELINE_ALL["property"].unique().tolist()) if isinstance(BASELINE_ALL, pd.DataFrame) and not BASELINE_ALL.empty else []
if not props_list:
    # keep selector but empty; user still sees warning in main
    sel_props = st.sidebar.multiselect("Seleziona struttura per l'analisi", [], default=[])
else:
    default_prop = props_list[0]
    sel_props = st.sidebar.multiselect("Seleziona struttura per l'analisi", props_list, default=[default_prop])

view_mode = st.sidebar.radio("Vista", ["Singola struttura","Aggregata"], index=0, horizontal=False)

# (B) Section: Carica i dati (left as-is; does not affect top KPIs)
st.sidebar.header("Carica i dati")
st.sidebar.selectbox("Struttura", props_list if props_list else ["—"], index=0)
st.sidebar.selectbox("Anno", [datetime.now().year-1, datetime.now().year, datetime.now().year+1], index=1)
st.sidebar.file_uploader("Drag and drop file here", type=["xlsx","xls","csv"])
c1, c2 = st.sidebar.columns(2)
c1.button("Carica file selezionati", use_container_width=True)
c2.button("Usa file demo", use_container_width=True)
st.sidebar.button("Svuota caricamenti", use_container_width=True)

# ---------------------------------------------------------------------
# Main – show KPIs from baseline if present
# ---------------------------------------------------------------------
if BASELINE_ALL is None or BASELINE_ALL.empty:
    st.warning("Baseline non trovato o vuoto: impossibile popolare la dashboard.")
    st.stop()

# determine active property (singola vista uses the first selected)
if view_mode == "Singola struttura":
    if not sel_props:
        st.warning("Seleziona almeno una struttura.")
        st.stop()
    active_prop = sel_props[0]
    df_view = BASELINE_ALL[BASELINE_ALL["property"] == active_prop].copy()
else:
    # Aggregata – somma tutte le strutture selezionate; se vuoto, tutte
    if sel_props:
        df_view = BASELINE_ALL[BASELINE_ALL["property"].isin(sel_props)].copy()
    else:
        df_view = BASELINE_ALL.copy()

if df_view.empty:
    st.warning("Nessun dato nel baseline per la selezione corrente.")
    st.stop()

# active month context
today = datetime.today()
active_y = today.year
active_m = today.month

def _fmt_eur(x: float) -> str:
    return ("€ {:,.2f}".format(x)).replace(",", "X").replace(".", ",").replace("X", ".")

def _compute_year_kpis(df: pd.DataFrame, year: int):
    dfy = df[df["year"] == year]
    if dfy.empty: 
        return {"revenue":0.0,"occ":0.0,"nights":0,"adr":0.0,"revpar":0.0}, {"revenue":0.0,"occ":0.0,"nights":0,"adr":0.0,"revpar":0.0}
    rooms_avail = None  # not available in baseline; occupancy derived if present
    revenue = float(dfy["revenue_total"].sum()) if "revenue_total" in dfy else 0.0
    nights = int(dfy["rooms_sold"].sum()) if "rooms_sold" in dfy else 0
    adr = float(pd.to_numeric(dfy["adr"], errors="coerce").mean()) if "adr" in dfy else 0.0
    revpar = float(pd.to_numeric(dfy["revpar"], errors="coerce").mean()) if "revpar" in dfy else 0.0
    # occ best-effort: if both revenue and adr exist we can't compute; prefer mean of occ% if present
    if "occ" in dfy:
        occ = float(pd.to_numeric(dfy["occ"], errors="coerce").mean())
    else:
        occ = 0.0
    # deltas YoY
    prev = df[df["year"] == (year-1)]
    def _pct(a,b): 
        if b==0: return 0.0
        return (a-b)
    deltas = {
        "revenue": _pct(revenue, float(prev["revenue_total"].sum()) if "revenue_total" in prev else 0.0),
        "nights":  _pct(nights, int(prev["rooms_sold"].sum()) if "rooms_sold" in prev else 0),
        "adr":     _pct(adr, float(pd.to_numeric(prev["adr"], errors="coerce").mean()) if "adr" in prev else 0.0),
        "revpar":  _pct(revpar, float(pd.to_numeric(prev["revpar"], errors="coerce").mean()) if "revpar" in prev else 0.0),
        "occ":     _pct(occ, float(pd.to_numeric(prev["occ"], errors="coerce").mean()) if "occ" in prev else 0.0),
    }
    return {"revenue":revenue,"occ":occ,"nights":nights,"adr":adr,"revpar":revpar}, deltas

def _kpi_cell(label: str, value: str, delta: float):
    pill = f'<span class="kpi-pill {"up" if delta>=0 else "down"}'>{("+" if delta>=0 else "")}{delta:,.2f}</span>'
    st.markdown(f"**{label}**  \n{value}  \n{pill}", unsafe_allow_html=True)

# YEAR KPIs
k_year, d_year = _compute_year_kpis(df_view, active_y)
c1, c2, c3, c4, c5 = st.columns(5)
with c1: _kpi_cell("Revenue anno", _fmt_eur(k_year["revenue"]), d_year["revenue"])
with c2: _kpi_cell("Occupazione", f"{k_year['occ']:.2f}%", d_year["occ"])
with c3: _kpi_cell("Notti vendute", f"{k_year['nights']:,}".replace(",", "."), float(d_year["nights"]))
with c4: _kpi_cell("ADR medio", _fmt_eur(k_year["adr"]), d_year["adr"])
with c5: _kpi_cell("RevPAR medio", _fmt_eur(k_year["revpar"]), d_year["revpar"])

# month header
def _nav_month_label(y,m):
    months = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    return f"{months[m-1]} {y}"

st.subheader(_nav_month_label(active_y, active_m))
df_curr = df_view[(df_view["year"]==active_y) & (df_view["month"]==active_m)]
if df_curr.empty:
    st.info("Nessun dato nel mese corrente nei baseline.")
else:
    rev = float(df_curr["revenue_total"].sum()) if "revenue_total" in df_curr else 0.0
    rooms = int(df_curr["rooms_sold"].sum()) if "rooms_sold" in df_curr else 0
    adr = float(pd.to_numeric(df_curr["adr"], errors="coerce").mean()) if "adr" in df_curr else 0.0
    revpar = float(pd.to_numeric(df_curr["revpar"], errors="coerce").mean()) if "revpar" in df_curr else 0.0
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Revenue mese", _fmt_eur(rev))
    with c2: st.metric("Notti vendute", f"{rooms:,}".replace(",", "."))
    with c3: st.metric("ADR medio", _fmt_eur(adr))
    with c4: st.metric("RevPAR medio", _fmt_eur(revpar))
