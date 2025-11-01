# -*- coding: utf-8 -*-
from __future__ import annotations

# --- Imports (tenere questa sezione compatta per permettere l'iniezione CSS subito sotto) ---
import io, os
import calendar
from datetime import datetime, date
from typing import Dict, Tuple, List

import pandas as pd
import streamlit as st

# Moduli progetto (presenti nel repository originale)
# Se in ambiente di test mancano, gestiamo un fallback "no-op" così l'app resta utilizzabile.
try:
    from baseline_loader import load_all_baselines, get_year_data, monthly_kpi
except Exception:  # pragma: no cover - fallback minimo per ambienti senza moduli
    def load_all_baselines() -> pd.DataFrame:
        return pd.DataFrame()
    def get_year_data(df_all: pd.DataFrame, prop_key: str, year: int) -> pd.DataFrame:
        if df_all.empty: 
            return pd.DataFrame()
        df = df_all[(df_all["property"] == prop_key) & (df_all["stay_date"].dt.year == year)].copy()
        return df
    def monthly_kpi(df_year: pd.DataFrame, month: int) -> Dict[str, float]:
        if df_year.empty: 
            return {"revenue":0.0,"occupied":0,"rooms_avail":0,"adr":0.0,"revpar":0.0}
        d = df_year[df_year["stay_date"].dt.month==month]
        rev = float(d["revenue_total"].sum())
        occ = int(pd.to_numeric(d.get("rooms_sold", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        rooms = int(pd.to_numeric(d.get("rooms_available", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        adr = float(pd.to_numeric(d.get("adr", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev/occ if occ>0 else 0))
        rpar= float(pd.to_numeric(d.get("revpar", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev/rooms if rooms>0 else 0))
        return {"revenue":rev,"occupied":occ,"rooms_avail":rooms,"adr":adr,"revpar":rpar}

try:
    from pickup_strip import render_pickup_next_11_months
except Exception:
    def render_pickup_next_11_months(prop_key: str):
        st.info("PickUp: modulo non disponibile in questa build di test.")
        return

# ---------------- Page config ----------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide")

# --- Sidebar styling (iniettato subito dopo gli import) ---
def _inject_sidebar_css():
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] .block-container { padding-top: 0.75rem; padding-bottom: 1rem; }
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3{
            font-weight:600 !important; font-size:0.95rem !important; letter-spacing:.02em;
            padding:8px 10px; margin:10px -8px 8px -8px; border-radius:6px;
            background:rgba(0,0,0,.04); border:1px solid rgba(0,0,0,.08);
        }
        [data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiSelect,
        [data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stDateInput,
        [data-testid="stSidebar"] .stNumberInput, [data-testid="stSidebar"] .stFileUploader,
        [data-testid="stSidebar"] button[kind="secondary"], [data-testid="stSidebar"] button[kind="primary"]{
            margin-top:4px; margin-bottom:10px;
        }
        [data-testid="stSidebar"] label{ font-weight:500; }
        [data-testid="stSidebar"] .stRadio > div{ row-gap: .25rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
_inject_sidebar_css()

CURRENCY = "€"

# ---------------- Baseline load (cache) ----------------
@st.cache_data(ttl=900, show_spinner=False)
def load_baseline_cached() -> pd.DataFrame:
    df = load_all_baselines()
    if df is None or df is ...:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty:
        return df
    # Types
    df = df.copy()
    df["stay_date"] = pd.to_datetime(df["stay_date"])
    for c in ["rooms_sold","revenue_total","adr","revpar","rooms_available"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

BASELINE_ALL = load_baseline_cached()

# ---------------- Session defaults (avoid empty home) ----------------
if "datasets" not in st.session_state:
    st.session_state["datasets"] = {}  # {(property_label, year): DataFrame}

if BASELINE_ALL is not None and not BASELINE_ALL.empty:
    preferred_order = ["Lavagnini", "La_Terrazza"]
    have = BASELINE_ALL["property"].dropna().unique().tolist()
    order = [p for p in preferred_order if p in have] or sorted(have)
    # map property key -> UI label
    ui_map = {"Lavagnini": "Lavagnini My Place", "La_Terrazza": "La Terrazza di Jenny"}
    default_prop_label = st.session_state.get("prop_view") or ui_map.get(order[0], order[0])
else:
    ui_map = {}
    default_prop_label = st.session_state.get("prop_view") or "Lavagnini My Place"

default_year = int(st.session_state.get("active_year") or datetime.now().year)
default_month = int(st.session_state.get("active_month") or datetime.now().month)
st.session_state.setdefault("active_year", default_year)
st.session_state.setdefault("active_month", default_month)
st.session_state.setdefault("prop_view", default_prop_label)

# ---------------- Sidebar: ordine richiesto ----------------
st.sidebar.header("streamlit app")
# Tab/placeholder (titoli, non logica di navigazione)
st.sidebar.markdown("• PickUp Catalogo")
st.sidebar.markdown("• PickUp Analisi")

# --- Sezione VISTA (seconda posizione) ---
st.sidebar.header("Vista")
# 1) Seleziona struttura per l'analisi
all_labels = sorted(set(ui_map.get(p,p) for p in (BASELINE_ALL["property"].unique().tolist() if not BASELINE_ALL.empty else ui_map.values())))
if not all_labels:  # fallback se baseline vuoto
    all_labels = ["Lavagnini My Place","La Terrazza di Jenny"]
props_to_use = st.sidebar.multiselect(
    "Seleziona struttura per l'analisi",
    options=all_labels,
    default=[st.session_state.get("prop_view", default_prop_label)],
    key="sb_prop_multi"
)
# 2) Vista (Singola/Aggregata)
_view_default = "Singola struttura" if len(props_to_use) <= 1 else "Aggregata"
view_mode = st.sidebar.radio("Vista", options=["Singola struttura","Aggregata"], index=0 if _view_default=="Singola struttura" else 1, key="view_mode")

# coerenza sessione
if props_to_use:
    st.session_state["prop_view"] = props_to_use[0]
st.session_state["props_to_use"] = props_to_use

# --- Sezione Carica i dati (spostata più in basso) ---
st.sidebar.header("Carica i dati")
prop_sel = st.sidebar.selectbox("Struttura", options=all_labels, index=all_labels.index(st.session_state["prop_view"]) if st.session_state["prop_view"] in all_labels else 0)
year_sel = st.sidebar.selectbox("Anno", options=[2024,2025,datetime.now().year], index=0 if default_year==2024 else (1 if default_year==2025 else 2))
upl = st.sidebar.file_uploader("Drag and drop file here", type=["xlsx"])

col_a, col_b = st.sidebar.columns(2)
with col_a:
    if st.button("Carica file selezionato", use_container_width=True):
        if upl is None:
            st.sidebar.warning("Seleziona un file prima di caricare.")
        else:
            st.sidebar.success("Upload ricevuto (parser disabilitato in questa build).")
with col_b:
    if st.button("Usa file demo", use_container_width=True):
        st.sidebar.info("Demo: caricamento locale abilitato nelle build con file di esempio.")

if st.sidebar.button("Svuota caricamenti"):
    st.session_state["datasets"] = {}
    st.sidebar.success("Caricamenti svuotati.")

# ---------------- Dataset di vista (aggregazione tra caricati e baseline) ----------------
def _assemble_df_view() -> pd.DataFrame:
    # Caricamenti utente
    frames: List[pd.DataFrame] = []
    for (label, y), df in st.session_state["datasets"].items():
        if df is not None and not df.empty:
            frames.append(df.copy())

    # Baseline -> rimappa a label UI e aggiungi colonne year/month
    if BASELINE_ALL is not None and not BASELINE_ALL.empty:
        map_lbl = {"Lavagnini": "Lavagnini My Place", "La_Terrazza": "La Terrazza di Jenny"}
        d = BASELINE_ALL.copy()
        d["property"] = d["property"].map(lambda k: map_lbl.get(k, k))
        d["year"] = d["stay_date"].dt.year
        d["month"] = d["stay_date"].dt.month
        # colonne alias che usa il resto della pagina
        d["revenue"] = pd.to_numeric(d.get("revenue_total", pd.Series(dtype=float)), errors="coerce")
        d["occupied"] = pd.to_numeric(d.get("rooms_sold", pd.Series(dtype=float)), errors="coerce")
        frames.append(d[["stay_date","year","month","property","revenue","occupied","rooms_available","adr","revpar"]])
    if frames:
        out = pd.concat(frames, ignore_index=True, sort=False)
        # normalizza tipi
        out["stay_date"] = pd.to_datetime(out["stay_date"])
        for c in ["revenue","occupied","rooms_available","adr","revpar","year","month"]:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce")
        return out
    return pd.DataFrame(columns=["stay_date","year","month","property","revenue","occupied","rooms_available","adr","revpar"])

df_all = _assemble_df_view()
if df_all.empty:
    st.warning("Baseline non trovato o vuoto: impossibile popolare la dashboard.")
    st.stop()

# Vista corrente
props_current = st.session_state.get("props_to_use") or [st.session_state["prop_view"]]
df_view = df_all[df_all["property"].isin(props_current)].copy()
if df_view.empty:
    st.warning("Nessun dato per la selezione corrente.")
    st.stop()

# ---------------- Header + navigazione anno/mese ----------------
def _month_labels(y: int, m: int):
    it = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    curr = f"{it[m-1]} {y}"
    pm, py = (12, y-1) if m == 1 else (m-1, y)
    nm, ny = (1, y+1) if m == 12 else (m+1, y)
    return curr, f"{it[pm-1]} {py}", f"{it[nm-1]} {ny}"

st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# Selettori rapidi anno/mese (allineati allo screenshot con frecce simulate)
y = int(st.session_state["active_year"]); m = int(st.session_state["active_month"])
month_label, prev_label, next_label = _month_labels(y, m)

c1, c2, c3 = st.columns([1,2,1])
with c1:
    if st.button("◀", key="mm_prev"):
        if m == 1:
            st.session_state["active_month"], st.session_state["active_year"] = 12, y-1
        else:
            st.session_state["active_month"] = m-1
with c3:
    if st.button("▶", key="mm_next"):
        if m == 12:
            st.session_state["active_month"], st.session_state["active_year"] = 1, y+1
        else:
            st.session_state["active_month"] = m+1
with c2:
    st.markdown(f"<h4 style='text-align:center;margin:0'>{month_label}</h4><div style='text-align:center;color:#6b7280'>(anno di comparazione: {y-1})</div>", unsafe_allow_html=True)

# ---------------- KPI Mese ----------------
def _fmt_eur(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY} {s}"
def _fmt_pct(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"
def _fmt_th(n: int) -> str:
    return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

df_cur  = df_view[(df_view["year"]==y) & (df_view["month"]==m)]
df_prev = df_view[(df_view["year"]==y-1) & (df_view["month"]==m)]

rev      = float(pd.to_numeric(df_cur.get("revenue", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
rev_py   = float(pd.to_numeric(df_prev.get("revenue", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
sold     = int(pd.to_numeric(df_cur.get("occupied", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
sold_py  = int(pd.to_numeric(df_prev.get("occupied", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
rooms    = int(pd.to_numeric(df_cur.get("rooms_available", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
rooms_py = int(pd.to_numeric(df_prev.get("rooms_available", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

adr     = float(pd.to_numeric(df_cur.get("adr", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev/sold if sold>0 else 0))
adr_py  = float(pd.to_numeric(df_prev.get("adr", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev_py/sold_py if sold_py>0 else 0))
rpar    = float(pd.to_numeric(df_cur.get("revpar", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev/rooms if rooms>0 else 0))
rpar_py = float(pd.to_numeric(df_prev.get("revpar", pd.Series(dtype=float)), errors="coerce").dropna().mean() or (rev_py/rooms_py if rooms_py>0 else 0))
occ     = (sold/rooms*100) if rooms>0 else 0.0
occ_py  = (sold_py/rooms_py*100) if rooms_py>0 else 0.0

cols = st.columns(5)
labels = ["Revenue anno","Occupazione","Notti vendute","ADR medio","RevPAR medio"]
values = [_fmt_eur(rev), _fmt_pct(occ), _fmt_th(sold), _fmt_eur(adr), _fmt_eur(rpar)]
deltas = [rev-rev_py, occ-occ_py, sold-sold_py, adr-adr_py, rpar-rpar_py]
for i,(lab,val,delta) in enumerate(zip(labels, values, deltas)):
    with cols[i]:
        st.markdown(f"**{lab}**")
        st.markdown(f"<h3 style='margin:4px 0 0 0'>{val}</h3>", unsafe_allow_html=True)
        color = "#15803d" if delta>=0 else "#b91c1c"
        sign  = "+" if delta>=0 else "–"
        disp  = f"{_fmt_eur(abs(delta)) if i in (0,3,4) else (_fmt_pct(abs(delta)) if i==1 else _fmt_th(abs(int(delta))))}"
        st.markdown(f"<span style='background:{'#ecfdf5' if delta>=0 else '#fef2f2'};border:1px solid {color};color:{color};padding:2px 6px;border-radius:999px;font-size:12px'>{sign} {disp}</span>", unsafe_allow_html=True)

st.markdown("---")

# ---------------- Sezione PickUp (richiama componente esterno) ----------------
# Determina chiave property tecnica per il modulo pickup
lab = st.session_state.get("prop_view","").lower()
if "lavagnini" in lab:
    prop_key = "Lavagnini"
elif "terrazza" in lab:
    prop_key = "La_Terrazza"
else:
    # prova a risalire dalla mappatura
    revmap = {v:k for k,v in ui_map.items()}
    prop_key = revmap.get(st.session_state.get("prop_view",""), "Lavagnini")
render_pickup_next_11_months(prop_key)
