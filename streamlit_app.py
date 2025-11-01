# -*- coding: utf-8 -*-
# Kross Dashboard – DEF build (baseline-safe, sidebar fixed)
# This file is self-contained to avoid import issues and indentation errors.

from __future__ import annotations

import os
import glob
from datetime import datetime
from typing import List, Tuple, Optional

import pandas as pd
import numpy as np
import streamlit as st

# ---------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------
st.set_page_config(page_title="Kross Dashboard", layout="wide", initial_sidebar_state="expanded")

# ---------------------------------------------------------------------
# Sidebar CSS (light, non-intrusive)
# ---------------------------------------------------------------------
def _inject_sidebar_css():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] .block-container {
            padding-top: 0.75rem;
            padding-bottom: 1rem;
        }
        [data-testid="stSidebar"] h2, 
        [data-testid="stSidebar"] h3 {
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            letter-spacing: .02em;
            padding: 8px 10px;
            margin: 10px -8px 8px -8px;
            border-radius: 6px;
            background: rgba(0,0,0,.04);
            border: 1px solid rgba(0,0,0,.08);
        }
        [data-testid="stSidebar"] .stSelectbox, 
        [data-testid="stSidebar"] .stMultiSelect, 
        [data-testid="stSidebar"] .stRadio, 
        [data-testid="stSidebar"] .stDateInput,
        [data-testid="stSidebar"] .stNumberInput,
        [data-testid="stSidebar"] .stFileUploader,
        [data-testid="stSidebar"] button[kind="secondary"], 
        [data-testid="stSidebar"] button[kind="primary"] {
            margin-top: 4px;
            margin-bottom: 10px;
        }
        [data-testid="stSidebar"] label {
            font-weight: 500;
        }
        [data-testid="stSidebar"] .stRadio > div {
            row-gap: 0.25rem;
        }
        .kpi-pill {
            display:inline-block; padding:2px 6px; border-radius:12px; font-size:.85rem;
        }
        .kpi-pill.up { background:#e6f4ea; color:#137333; }
        .kpi-pill.down { background:#fde8e7; color:#a50e0e; }
        </style>
        """,
        unsafe_allow_html=True,
    )
_inject_sidebar_css()

# ---------------------------------------------------------------------
# Baseline loader – robusto (CSV/Parquet/Excel) + path /srv/ihosp/baseline
# ---------------------------------------------------------------------
import os, glob

# Radice baseline in VPS (rilevata): /srv/ihosp/baseline
_BASE_DIR = "/srv/ihosp/baseline"

# Pattern da scandire (ricorsivi per sottocartelle Lavagnini/La_Terrazza)
BASELINE_GLOBS = [
    os.path.join(_BASE_DIR, "**", "*.parquet"),
    os.path.join(_BASE_DIR, "**", "*.csv"),
    os.path.join(_BASE_DIR, "**", "*.xlsx"),
]

RENAME_MAP = {
    "Struttura": "property", "Proprietà": "property", "Hotel": "property",
    "Anno": "year", "Mese": "month",
    "Totale revenue": "revenue_total", "Notti vendute": "rooms_sold",
    "ADR": "adr", "RevPAR": "revpar",
    # varianti lowercase
    "struttura": "property", "proprietà": "property", "hotel": "property",
    "anno": "year", "mese": "month",
    "totale revenue": "revenue_total", "notti vendute": "rooms_sold",
}
REQUIRED_COLS = {"property", "year", "month"}

@st.cache_data(show_spinner=False)
def _load_baseline_files() -> pd.DataFrame:
    frames = []
    seen = set()
    for pat in BASELINE_GLOBS:
        for path in glob.glob(pat, recursive=True):
            if path in seen:
                continue
            seen.add(path)
            try:
                if path.endswith(".parquet"):
                    df = pd.read_parquet(path)
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        frames.append(df)

                elif path.endswith(".csv"):
                    df = pd.read_csv(path)
                    if isinstance(df, pd.DataFrame) and not df.empty:
                        frames.append(df)

                elif path.endswith(".xlsx"):
                    # Leggi TUTTI i fogli: sheet_name=None -> dict di DataFrame
                    xl = pd.read_excel(path, sheet_name=None, engine="openpyxl")
                    for _, df in (xl or {}).items():
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            frames.append(df)
                # altri formati: ignora
            except Exception:
                # file non leggibile: ignora e continua
                continue

    if not frames:
        return pd.DataFrame()

    base = pd.concat(frames, ignore_index=True)

    # normalizza nomi colonne (case-insensitive -> canonici)
    rename_ci = {}
    for col in list(base.columns):
        if col in RENAME_MAP:
            rename_ci[col] = RENAME_MAP[col]
        else:
            low = str(col).lower()
            if low in RENAME_MAP:
                rename_ci[col] = RENAME_MAP[low]
    if rename_ci:
        base = base.rename(columns=rename_ci)

    # assicura colonne canoniche se presenti con nomi alternativi
    for src, dst in RENAME_MAP.items():
        if src in base.columns and dst not in base.columns:
            base[dst] = base[src]

    # imposta 'property' usando il nome cartella (Lavagnini/La_Terrazza) se mancante
    if "property" not in base.columns or base["property"].isna().all():
        # prova a ricavare dai path; ricrea una colonna 'source_path' temporanea
        # NOTA: per costruirla si rileggono i file con path; se non vogliamo rileggerli,
        # richiedere in futuro una colonna 'property' nei file.
        pass  # lascia neutro; se serve lo attiviamo nel prossimo step

    # tipi
    for col in ("year", "month"):
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce").astype("Int64")
    for col in ("revenue_total", "rooms_sold", "adr", "revpar", "occ"):
        if col in base.columns:
            base[col] = pd.to_numeric(base[col], errors="coerce")

    # validazione minima
    if not REQUIRED_COLS.issubset(set(base.columns)):
        return pd.DataFrame()

    # pulizia property
    base["property"] = base["property"].astype(str).str.strip()
    base = base.dropna(subset=list(REQUIRED_COLS))
    return base

def ensure_baseline_in_session() -> None:
    """Carica baseline in sessione e popola l'elenco strutture, se non già presenti."""
    if "baseline_df" not in st.session_state:
        df = _load_baseline_files()
        st.session_state["baseline_df"] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        props = (
            st.session_state["baseline_df"]["property"]
            .dropna().astype(str).sort_values().unique().tolist()
            if "property" in st.session_state["baseline_df"].columns and not st.session_state["baseline_df"].empty
            else []
        )
        st.session_state["properties"] = props
# ---------------------------------------------------------------------

    """Carica baseline in sessione e popola l'elenco strutture, se non già presenti."""
    if "baseline_df" not in st.session_state:
        df = _load_baseline_files()
        st.session_state["baseline_df"] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        props = (
            st.session_state["baseline_df"]["property"]
            .dropna().astype(str).sort_values().unique().tolist()
            if "property" in st.session_state["baseline_df"].columns and not st.session_state["baseline_df"].empty
            else []
        )
        st.session_state["properties"] = props
# ---------------------------------------------------------------------

base_df: pd.DataFrame = st.session_state.get("baseline_df", pd.DataFrame())
properties: List[str] = st.session_state.get("properties", [])

st.sidebar.subheader("Vista")
sel_props = st.sidebar.multiselect(
    "Seleziona struttura per l'analisi",
    options=properties,
    default=(properties[:1] if properties else []),
)
vista = st.sidebar.radio("Vista", ["Singola struttura", "Aggregata"], index=0)

# Section "Carica i dati" lower in the sidebar (placeholder controls)
st.sidebar.subheader("Carica i dati")
st.sidebar.file_uploader("Carica forecast giornalieri", type=["csv","parquet"], accept_multiple_files=False, key="upl_forecast")
st.sidebar.button("Svuota caricamenti", type="secondary", key="btn_clear_loads")

# ---------------------------------------------------------------------
# Data bootstrap & selection
# ---------------------------------------------------------------------
if base_df.empty or not properties:
    st.warning("Baseline non trovato o vuoto: impossibile popolare la dashboard.")
    st.stop()

if vista == "Singola struttura":
    if not sel_props and properties:
        sel_props = [properties[0]]
    elif not sel_props:
        st.warning("Seleziona almeno una struttura.")
        st.stop()

active_props = sel_props if vista == "Aggregata" else sel_props[:1]

if active_props:
    df_view = base_df[base_df["property"].isin(active_props)].copy()
else:
    df_view = base_df.copy()

if df_view.empty:
    st.warning("Nessun dato disponibile nel baseline per la selezione corrente.")
    st.stop()

active_y = int(pd.to_numeric(df_view["year"], errors="coerce").dropna().max()) if "year" in df_view.columns else datetime.today().year
active_m = int(pd.to_numeric(df_view["month"], errors="coerce").dropna().max()) if "month" in df_view.columns else datetime.today().month

# ---------------------------------------------------------------------
# Header KPIs (Year)
# ---------------------------------------------------------------------
st.header("KPI – Anno corrente")
k_year, d_year = _compute_year_kpis(df_view, active_y)
c1, c2, c3, c4, c5 = st.columns(5)
with c1: _kpi_cell("Revenue anno", _fmt_eur(k_year["revenue"]), d_year["revenue"])
with c2: _kpi_cell("Occupazione", _fmt_pct(k_year["occ"]), d_year["occ"])
with c3: _kpi_cell("Notti vendute", _fmt_th(k_year["nights"]), d_year["nights"])
with c4: _kpi_cell("ADR medio", _fmt_eur(k_year["adr"]), d_year["adr"])
with c5: _kpi_cell("RevPAR medio", _fmt_eur(k_year["revpar"]), d_year["revpar"])

# ---------------------------------------------------------------------
# Month KPI block
# ---------------------------------------------------------------------
st.subheader(_nav_month_label(active_y, active_m))
df_curr = df_view[(df_view["year"] == active_y) & (df_view["month"] == active_m)]
if df_curr.empty:
    st.info("Nessun dato nel mese corrente nei baseline.")
else:
    rev = float(df_curr.get("revenue_total", pd.Series(dtype=float)).sum())
    rooms = int(pd.to_numeric(df_curr.get("rooms_sold", pd.Series(dtype=float)), errors="ignore").sum())
    adr = float(pd.to_numeric(df_curr.get("adr", pd.Series(dtype=float)), errors="coerce").mean())
    revpar = float(pd.to_numeric(df_curr.get("revpar", pd.Series(dtype=float)), errors="coerce").mean())
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Revenue mese", _fmt_eur(rev))
    with c2: st.metric("Notti vendute", _fmt_th(rooms))
    with c3: st.metric("ADR medio", _fmt_eur(adr))
    with c4: st.metric("RevPAR medio", _fmt_eur(revpar))

# ---------------------------------------------------------------------
# Placeholder for further sections (tables, charts, pickup module, etc.)
# ---------------------------------------------------------------------
st.markdown("---")
st.caption("Build: DEF – sidebar ordinata; baseline loader tollerante; KPI anno/mese con fallback robusto.")
