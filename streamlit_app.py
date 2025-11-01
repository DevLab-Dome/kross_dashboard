# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import List, Dict, Tuple, Optional

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# IMPORTS DI MODULO (tolleranti: l'app non deve rompersi se mancano moduli)
# -----------------------------------------------------------------------------
try:
    from modules.data_loader import load_config, normalize_wide_excel
except Exception as e:
    # fallback minimi per non esplodere in ambienti di test
    def load_config(path: str) -> dict:
        return {"rooms_default": 5, "rooms_per_property": {}, "currency_symbol": "€"}
    def normalize_wide_excel(file_like, cfg: dict, prop_label: str) -> pd.DataFrame:
        # fallback: prova a leggere come Excel "lungo standard"
        df = pd.read_excel(file_like)
        # normalizza colonne minime attese
        colmap = {
            "stay_date": "stay_date",
            "date": "stay_date",
            "property": "property",
            "revenue_total": "revenue",
            "revenue": "revenue",
            "rooms_sold": "occupied",
            "occupied": "occupied",
            "adr": "adr",
            "revpar": "revpar",
        }
        df = df.rename(columns={k: v for k, v in colmap.items() if k in df.columns})
        if "stay_date" in df.columns:
            df["stay_date"] = pd.to_datetime(df["stay_date"]).dt.date
            df["year"] = pd.to_datetime(df["stay_date"]).dt.year
            df["month"] = pd.to_datetime(df["stay_date"]).dt.month
        if "property" not in df.columns:
            df["property"] = prop_label
        return df

try:
    from baseline_loader import load_all_baselines, get_year_data
except Exception:
    def load_all_baselines() -> pd.DataFrame:
        # tenta di caricare baseline da file locali noti (se presenti)
        files = [
            "/mnt/data/Lavagnini_Forecast_01012024_31122024.xlsx",
            "/mnt/data/Lavagnini_Forecast_01012025_31122025.xlsx",
            "/mnt/data/La_Terrazza_Forecast_01092024_31122024.xlsx",
            "/mnt/data/La_Terrazza_Forecast_01012025_31122025.xlsx",
        ]
        frames = []
        for path in files:
            if os.path.exists(path):
                prop = "Lavagnini" if "Lavagnini" in os.path.basename(path) else "La_Terrazza"
                with open(path, "rb") as f:
                    df = normalize_wide_excel(io.BytesIO(f.read()), {}, prop)
                frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def get_year_data(df: pd.DataFrame, prop_key: str, year: int) -> pd.DataFrame:
        if df is None or df.empty: return pd.DataFrame()
        return df[(df["property"].str.contains(prop_key, case=False, na=False)) & (df["year"] == year)].copy()

try:
    from pickup_strip import render_pickup_next_11_months
except Exception:
    def render_pickup_next_11_months(prop_key: str):
        st.info(f"Pickup view non disponibile (modulo non importabile). Prop: {prop_key}")

# -----------------------------------------------------------------------------
# STILI BASE + SIDEBAR CSS
# -----------------------------------------------------------------------------
def _inject_base_styles():
    st.markdown("""
    <style>
    .dl-root{ padding:0; margin:0 }
    /* KPI pill base */
    .kpi-pill{display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .6rem;border-radius:999px;border:1px solid rgba(0,0,0,.08);font-weight:600}
    .kpi-pill.up{background:#ecfdf5;color:#065f46}.kpi-pill.down{background:#fef2f2;color:#dc2626}
    </style>
    """, unsafe_allow_html=True)

def _inject_sidebar_css():
    st.markdown("""
    <style>
    [data-testid="stSidebar"] .block-container{padding-top:.75rem;padding-bottom:1rem}
    [data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{
        font-weight:600!important;font-size:.95rem!important;letter-spacing:.02em;
        padding:8px 10px;margin:10px -8px 8px -8px;border-radius:6px;
        background:rgba(0,0,0,.04);border:1px solid rgba(0,0,0,.08);
    }
    [data-testid="stSidebar"] .stSelectbox, 
    [data-testid="stSidebar"] .stMultiSelect, 
    [data-testid="stSidebar"] .stRadio, 
    [data-testid="stSidebar"] .stDateInput,
    [data-testid="stSidebar"] .stNumberInput,
    [data-testid="stSidebar"] .stFileUploader,
    [data-testid="stSidebar"] button[kind="secondary"], 
    [data-testid="stSidebar"] button[kind="primary"]{margin-top:4px;margin-bottom:10px}
    [data-testid="stSidebar"] label{font-weight:500}
    [data-testid="stSidebar"] .stRadio>div{row-gap:.25rem}
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE CONFIG + STILI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="expanded")
_inject_base_styles()
_inject_sidebar_css()
st.markdown('<div class="dl-root"></div>', unsafe_allow_html=True)
st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# -----------------------------------------------------------------------------
# CONFIG & STATE
# -----------------------------------------------------------------------------
CFG = load_config("config.yaml")
CURRENCY = CFG.get("currency_symbol", "€")
ROOMS_DEFAULT = int(CFG.get("rooms_default", 5))
ROOMS_MAP: Dict[str, int] = CFG.get("rooms_per_property", {})

today = datetime.now()
st.session_state.setdefault("active_year", today.year)
st.session_state.setdefault("active_month", today.month)
st.session_state.setdefault("datasets", {})

PROPERTIES_UI = ["Lavagnini My Place", "La Terrazza di Jenny"]
YEARS_UI = [2024, 2025]

# -----------------------------------------------------------------------------
# BASELINE: caricamento una volta
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def _load_baseline_all() -> pd.DataFrame:
    df = load_all_baselines()
    if df is not None and not df.empty:
        # normalizza tipi
        if "stay_date" in df.columns:
            df["stay_date"] = pd.to_datetime(df["stay_date"]).dt.date
            dt = pd.to_datetime(df["stay_date"])
            df["year"] = dt.dt.year
            df["month"] = dt.dt.month
        for c in ["rooms_sold","occupied","revenue_total","revenue","adr","revpar"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        # colonne canoniche
        df = df.rename(columns={
            "revenue_total": "revenue",
            "rooms_sold": "occupied",
        })
        if "property" not in df.columns:
            df["property"] = ""
    return df if df is not None else pd.DataFrame()

BASELINE_ALL = _load_baseline_all()

# -----------------------------------------------------------------------------
# POPOLAMENTO DATI IN SESSIONE DA BASELINE (se vuoto)
# -----------------------------------------------------------------------------
if BASELINE_ALL is not None and not BASELINE_ALL.empty and not st.session_state["datasets"]:
    # Prendi due properties se disponibili, per 2024-2025
    for prop_key in sorted(BASELINE_ALL["property"].dropna().unique().tolist())[:2]:
        for yr in [2024, 2025]:
            dfy = get_year_data(BASELINE_ALL, prop_key, yr)
            if dfy is not None and not dfy.empty:
                # mappa label UI
                label = "Lavagnini My Place" if "lavagnini" in prop_key.lower() else "La Terrazza di Jenny"
                # colonne finali
                keep = [c for c in ["property","stay_date","year","month","revenue","occupied","adr","revpar"] if c in dfy.columns]
                st.session_state["datasets"][(label, int(yr))] = dfy[keep].copy()

# -----------------------------------------------------------------------------
# ======= SIDEBAR =======
# 1) (TOP) – Tabs nella pagina principale (non in sidebar)
# 2) (SECOND) – Sezione "Vista": Seleziona struttura per l'analisi -> Vista
# 3) (LOWER) – Sezione "Carica i dati" (uploader, demo, svuota)
# -----------------------------------------------------------------------------
st.sidebar.header("Vista")  # sezione 2
# Seleziona struttura per l'analisi
all_props = sorted({k[0] for k in st.session_state["datasets"].keys()} or PROPERTIES_UI)
struttura_sel = st.sidebar.selectbox("Seleziona struttura per l'analisi", options=all_props, index=0, key="struttura_sel")

# Vista: singola/aggregata
view_options = ["Singola struttura", "Aggregata"]
current_vm = st.session_state.get("view_mode", view_options[0])
view_mode = st.sidebar.radio("Vista", options=view_options, index=view_options.index(current_vm) if current_vm in view_options else 0, key="view_mode")

# --- Sezione Carica i dati (più in basso) ---
st.sidebar.header("Carica i dati")
prop_sel = st.sidebar.selectbox("Struttura", options=PROPERTIES_UI, index=all_props.index(struttura_sel) if struttura_sel in all_props else 0)
year_sel = st.sidebar.selectbox("Anno", options=YEARS_UI, index=YEARS_UI.index(st.session_state["active_year"]) if st.session_state["active_year"] in YEARS_UI else 0)
upl = st.sidebar.file_uploader(f"File {prop_sel} – {year_sel}", type=["xlsx"], key=f"uploader_{prop_sel}_{year_sel}")
col_a, col_b = st.sidebar.columns(2)
with col_a:
    if st.button("Carica file selezionato", use_container_width=True):
        if upl is None:
            st.sidebar.warning("Seleziona un file prima di caricare.")
        else:
            data = upl.read()
            dfu = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
            dfu = dfu[dfu["year"] == year_sel].copy() if "year" in dfu.columns else dfu.copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = dfu
            st.sidebar.success(f"Caricato: {prop_sel} – {year_sel} ({len(dfu)} righe)")
with col_b:
    demo_map = {
        ("Lavagnini My Place", 2024): "/mnt/data/Lavagnini_Forecast_01012024_31122024.xlsx",
        ("Lavagnini My Place", 2025): "/mnt/data/Lavagnini_Forecast_01012025_31122025.xlsx",
        ("La Terrazza di Jenny", 2024): "/mnt/data/La_Terrazza_Forecast_01092024_31122024.xlsx",
        ("La Terrazza di Jenny", 2025): "/mnt/data/La_Terrazza_Forecast_01012025_31122025.xlsx",
    }
    if st.button("Usa file demo", use_container_width=True):
        path = demo_map.get((prop_sel, year_sel))
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                dfd = normalize_wide_excel(io.BytesIO(f.read()), CFG, prop_sel)
            dfd = dfd[dfd["year"] == year_sel].copy() if "year" in dfd.columns else dfd.copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = dfd
            st.sidebar.success(f"Demo caricata: {prop_sel} – {year_sel} ({len(dfd)} righe)")
        else:
            st.sidebar.warning("Demo non disponibile per la combinazione scelta.")

st.sidebar.markdown("---")
if st.sidebar.button("Svuota caricamenti"):
    st.session_state["datasets"].clear()
    st.sidebar.info("Caricamenti svuotati.")

# -----------------------------------------------------------------------------
# DATI PER LA VISTA
# -----------------------------------------------------------------------------
if not st.session_state["datasets"]:
    st.warning("Nessun dato disponibile. Carica un file o usa la demo.")
    st.stop()

df_all = pd.concat(st.session_state["datasets"].values(), ignore_index=True)
if view_mode == "Singola struttura":
    df_view = df_all[df_all["property"].str.contains("lavagnini", case=False, na=False) if "Lavagnini" in struttura_sel else df_all["property"].str.contains("terrazza", case=False, na=False)].copy()
else:
    df_view = df_all.copy()

# set attivi (mese/anno)
st.session_state["active_year"] = int(st.session_state.get("active_year") or today.year)
st.session_state["active_month"] = int(st.session_state.get("active_month") or today.month)
active_y = st.session_state["active_year"]
active_m = st.session_state["active_month"]

# -----------------------------------------------------------------------------
# TABS PRIMA POSIZIONE (main content)
# -----------------------------------------------------------------------------
tab_streamlit, tab_pickup = st.tabs(["Streamlit", "Pickup"])

with tab_streamlit:
    st.subheader("Panoramica mese attivo")
    # filtro mese corrente
    if "year" in df_view.columns and "month" in df_view.columns:
        df_cur = df_view[(df_view["year"] == active_y) & (df_view["month"] == active_m)].copy()
    else:
        df_cur = df_view.copy()

    if df_cur.empty:
        st.info("Nessun dato per mese/anno selezionato.")
    else:
        # KPI base
        revenue = pd.to_numeric(df_cur["revenue"], errors="coerce").sum() if "revenue" in df_cur.columns else 0.0
        occ = pd.to_numeric(df_cur["occupied"], errors="coerce").sum() if "occupied" in df_cur.columns else 0.0
        adr = pd.to_numeric(df_cur["adr"], errors="coerce").mean() if "adr" in df_cur.columns else 0.0
        revpar = pd.to_numeric(df_cur["revpar"], errors="coerce").mean() if "revpar" in df_cur.columns else 0.0
        st.write(f"**Revenue:** {CURRENCY} {revenue:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.write(f"**Occupancy (rooms sold):** {int(occ)}")
        st.write(f"**ADR:** {CURRENCY} {adr:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.write(f"**RevPAR:** {CURRENCY} {revpar:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

with tab_pickup:
    # Mappatura semplice label UI -> chiave tecnica
    lab = struttura_sel.lower()
    if "lavagnini" in lab:
        prop_key = "Lavagnini"
    elif "terrazza" in lab:
        prop_key = "La_Terrazza"
    else:
        prop_key = struttura_sel
    render_pickup_next_11_months(prop_key)

# -----------------------------------------------------------------------------
# FINE FILE
# -----------------------------------------------------------------------------
