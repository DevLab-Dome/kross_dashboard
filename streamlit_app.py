# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import io
from datetime import datetime
from typing import List

import pandas as pd
import streamlit as st

# ===== BASELINE LOADER (tollerante) =====
import os, glob
import pandas as pd
import streamlit as st

BASELINE_GLOBS = [
    "/opt/kross_dashboard_dev/data/baseline/*.parquet",
    "/opt/kross_dashboard_dev/data/baseline/*.csv",
    "data/baseline/*.parquet",
    "data/baseline/*.csv",
    "baseline/*.parquet",
    "baseline/*.csv",
]

RENAME_MAP = {
    "Struttura": "property",
    "Proprietà": "property",
    "Hotel": "property",
    "Anno": "year",
    "Mese": "month",
    "Totale revenue": "revenue_total",
    "Notti vendute": "rooms_sold",
    "ADR": "adr",
    "RevPAR": "revpar",
}

REQUIRED_COLS = {"property", "year", "month"}

@st.cache_data(show_spinner=False)
def _load_baseline_files() -> pd.DataFrame:
    frames = []
    for pat in BASELINE_GLOBS:
        for path in glob.glob(pat):
            try:
                if path.endswith(".parquet"):
                    df = pd.read_parquet(path)
                else:
                    df = pd.read_csv(path)
                if not isinstance(df, pd.DataFrame) or df.empty:
                    continue
                # normalizza colonne
                cols_lower = {c.lower(): c for c in df.columns}
                # rinomina da mappa (se presenti)
                ren = {src: RENAME_MAP[src] for src in RENAME_MAP if src in df.columns}
                if ren:
                    df = df.rename(columns=ren)
                # se le chiavi base non ci sono in chiaro, prova in lower
                if not REQUIRED_COLS.issubset(set(df.columns)):
                    # tenta da lower-case
                    if {"property","year","month"}.issubset(set(k.lower() for k in df.columns)):
                        df.columns = [RENAME_MAP.get(c, c) for c in df.columns]
                frames.append(df)
            except Exception:
                # passa oltre file malformati
                continue

    if not frames:
        return pd.DataFrame()

    base = pd.concat(frames, ignore_index=True)

    # assicurati delle colonne minime
    for src, dst in RENAME_MAP.items():
        if src in base.columns and dst not in base.columns:
            base[dst] = base[src]

    # enforce tipi
    for col in ("year", "month"):
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").astype("Int64")

    # colonne KPI opzionali → numeric
    for col in ("revenue_total", "rooms_sold", "adr", "revpar"):
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce")

    # filtra righe valide
    if REQUIRED_COLS.issubset(set(base.columns)):
        base = base.dropna(subset=list(REQUIRED_COLS))
    else:
        # schema non valido
        return pd.DataFrame()

    return base


def ensure_baseline_in_session() -> None:
    """Carica baseline in sessione se mancante, e popola la lista strutture."""
    if "baseline_df" not in st.session_state:
        df = _load_baseline_files()
        if df is None or df.empty:
            st.session_state["baseline_df"] = pd.DataFrame()
            st.session_state["properties"] = []
            return
        st.session_state["baseline_df"] = df
        # elenco strutture
        props = (
            df["property"].dropna().astype(str).sort_values().unique().tolist()
            if "property" in df.columns else []
        )
        st.session_state["properties"] = props
# ===== FINE BASELINE LOADER =====

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
    # ---- Bootstrap dati baseline in sessione ----
    pass
ensure_baseline_in_session()
base_df: pd.DataFrame = st.session_state.get("baseline_df", pd.DataFrame())
properties = st.session_state.get("properties", [])

# Sidebar — Seleziona struttura per l'analisi
st.sidebar.subheader("Vista")
sel_props = st.sidebar.multiselect(
    "Seleziona struttura per l'analisi",
    options=properties,
    default=(properties[:1] if properties else []),
)

# Se il baseline è vuoto, mostra un avviso e interrompe il render (evita pagina bianca)
if base_df.empty or not properties:
    st.warning("Baseline non trovato o vuoto: impossibile popolare la dashboard.")
    st.stop()


# Vista (singola/aggregata)
vista = st.sidebar.radio("Vista", ["Singola struttura", "Aggregata"], index=0)

# ---- Costruisci il sottoinsieme dati da baseline in base alla selezione ----
if sel_props:
    df_view = base_df[base_df["property"].isin(active_props)].copy()
else:
    # nessuna selezione → usa tutto il baseline
    df_view = base_df.copy()

# se ancora vuoto, interrompi in modo chiaro (evita dashboard “bianca”)
if df_view.empty:
    st.warning("Nessun dato disponibile nel baseline per la selezione corrente.")
    st.stop()

# ---- Anno/mese attivi (fallback robusto) ----
if "year" in df_view.columns:
    active_y = int(pd.to_numeric(df_view["year"], errors="coerce").dropna().max())
else:
    active_y = pd.Timestamp.today().year

if "month" in df_view.columns:
    active_m = int(pd.to_numeric(df_view["month"], errors="coerce").dropna().max())
else:
    active_m = pd.Timestamp.today().month
# determine active property (singola vista uses the first selected)
if vista == "Singola struttura":
    if not sel_props and properties:
        # fallback: seleziona automaticamente la prima struttura disponibile
        sel_props = [properties[0]]
    elif not sel_props:
        st.warning("Seleziona almeno una struttura.")
        st.stop()

# props effettive da usare nel filtro dati
active_props = sel_props if vista == "Aggregata" else sel_props[:1]
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

def _kpi_cell(label: str, value: str, delta: float | None):
    # Render di una cella KPI con pillola verde/rossa
    cls = "up" if (delta is not None and delta >= 0) else "down"
    sign = "+" if (delta is not None and delta >= 0) else ""
    pill = "" if delta is None else f'<span class="kpi-pill {cls}">{sign}{delta:,.2f}</span>'
    st.markdown(f"**{label}**  \n{value}  \n{pill}", unsafe_allow_html=True)

# YEAR KPIs
k_year, d_year = _compute_year_kpis(df_view, active_y)
c1, c2, c3, c4, c5 = st.columns(5)
with c1: _kpi_cell("Revenue anno", _fmt_eur(k_year["revenue"]), d_year["revenue"])
with c2: _kpi_cell("Occupazione", f"{k_year['occ']:.2f}%", d_year["occ"])
with c3: _kpi_cell("Notti vendute", f"{k_year['nights']:,}".replace(",", "."), float(d_year["nights"]) if d_year["nights"] is not None else None)
with c4: _kpi_cell("ADR medio", _fmt_eur(k_year["adr"]), d_year["adr"])
with c5: _kpi_cell("RevPAR medio", _fmt_eur(k_year["revpar"]), d_year["revpar"])

# month header
def _nav_month_label(y, m):
    months = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    return f"{months[m-1]} {y}"
