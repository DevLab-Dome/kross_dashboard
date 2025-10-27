# -*- coding: utf-8 -*-
from __future__ import annotations

import io, os
from datetime import datetime

import pandas as pd
import streamlit as st

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

div.stButton>button{
    padding: var(--dl-pad);
    border-radius: 8px; border:1px solid #cbd5e1;
    background:#fff !important; color: var(--dl-fg) !important; font-weight: 600;
    transition: border-color .12s ease, box-shadow .12s ease;
    white-space: nowrap; min-width: 96px;
}
div.stButton>button:hover{ border-color: var(--dl-accent); box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:focus{ outline:none; box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:disabled{
    background: var(--dl-chip-bg) !important; color: var(--dl-chip-fg) !important;
    border-color: #cbd5e1 !important; font-weight: 700 !important;
    cursor: default !important; opacity: 1 !important; box-shadow: none !important;
}

/* Header mese */
.mh-under{color:#0f172a;opacity:.6;font-size:15px;text-align:center;margin-top:2px;}
.mh-center{text-align:center;margin-top:2px;}
.mh-month{font-weight:700;font-size:28px;line-height:1.1;margin:0;}
.mh-sub{color:#6b7280;font-size:13px;margin-top:2px;}
div.mh-btn{ margin-bottom:2px; }
div.mh-btn > button{
  border:1px solid #e5e7eb !important; border-radius:10px !important;
  background:#ffffff !important; font-weight:700 !important; font-size:18px !important;
  min-height:44px; min-width:120px; margin-bottom:0 !important;
}
div.mh-btn > button:hover{
  border-color:#1f6feb !important; box-shadow:0 0 0 3px rgba(31,111,235,.25) !important;
}

/* KPI mese */
.kpi-col{ width:100%; display:flex; flex-direction:column; align-items:center; }
.kpi-label{ font-size:14px; color:#6b7280; margin-bottom:6px; white-space:nowrap; }
.kpi-value{ font-size:36px; font-weight:700; color:#111827; line-height:1.15; white-space:nowrap; }
.kpi-pill{ display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px;
           font-size:13px; font-weight:600; margin-top:8px; }
.kpi-pill.up{ background:#ecfdf5; color:#16a34a; }
.kpi-pill.down{ background:#fef2f2; color:#dc2626; }
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
ROOMS_DEFAULT = int(CFG.get("rooms_default", 5))
ROOMS_MAP: dict = CFG.get("rooms_per_property", {})

CURRENCY = CFG.get("currency_symbol", "€")

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

upl = st.sidebar.file_uploader(f"File {prop_sel} – {year_sel}", type=["xlsx"], key=f"uploader_{prop_sel}_{year_sel}")
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
# KPI MESE (formattazioni + calcolo robusto)
# -----------------------------------------------------------------------------
def _fmt_eur(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY} {s}"
def _fmt_pct(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"
def _fmt_th(n: int) -> str:
    return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

def _first_sum(df: pd.DataFrame, cands: list[str]) -> float:
    if df is None or df.empty: return 0.0
    for c in cands:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce").sum()
            if pd.notna(v): return float(v)
    return 0.0

def _first_mean(df: pd.DataFrame, cands: list[str]) -> float:
    if df is None or df.empty: return 0.0
    for c in cands:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce").mean()
            if pd.notna(v): return float(v)
    return 0.0

def _rooms_avail_fallback(df_month_like: pd.DataFrame, year: int, month: int) -> float:
    """Se mancano 'rooms_available', calcola: camere_per_struttura × giorni_del_mese, sommato sulle strutture presenti."""
    if df_month_like is None or df_month_like.empty: 
        return 0.0
    days = pd.Period(f"{year}-{month:02d}").days_in_month
    props = (df_month_like["property"].dropna().unique().tolist() 
             if "property" in df_month_like.columns else [])
    if not props:  # se non ci sono proprietà nel DF (edge case), usa selezione corrente se disponibile
        props = []
    total = 0.0
    for p in props:
        rooms = int(ROOMS_MAP.get(p, ROOMS_DEFAULT))
        total += rooms * days
    return float(total)

# Sottoinsiemi anno/mese corrente e stesso mese anno precedente
df_cur  = df_view[(df_view["year"] == active_y)     & (df_view["month"] == active_m)].copy()
df_prev = df_view[(df_view["year"] == active_y - 1) & (df_view["month"] == active_m)].copy()

# Notti vendute (somma) – prova più nomi di colonna
sold_nights    = int(round(_first_sum(df_cur,  ["occupied","notti","nights","rooms_sold","sold_nights"])))
sold_nights_py = int(round(_first_sum(df_prev, ["occupied","notti","nights","rooms_sold","sold_nights"])))

# Camere disponibili – usa la colonna se c'è, altrimenti fallback da config
rooms_avail    = _first_sum(df_cur,  ["rooms_available","rooms_avail","camere_disponibili"])
rooms_avail_py = _first_sum(df_prev, ["rooms_available","rooms_avail","camere_disponibili"])
if rooms_avail == 0.0:
    rooms_avail    = _rooms_avail_fallback(df_cur,  active_y,     active_m)
if rooms_avail_py == 0.0:
    rooms_avail_py = _rooms_avail_fallback(df_prev, active_y - 1, active_m)

# Revenue (somma), ADR/RevPAR (media giornaliera)
revenue    = _first_sum(df_cur,  ["revenue","totale_revenue","ricavi"])
revenue_py = _first_sum(df_prev, ["revenue","totale_revenue","ricavi"])
# --- ADR: prima formula (Revenue / Notti vendute), altrimenti media colonna se disponibile
adr_calc    = (revenue / sold_nights)       if sold_nights    > 0 else 0.0
adr_col     = _first_mean(df_cur,  ["adr","ADR"])
adr         = adr_calc if adr_calc > 0 else (adr_col or 0.0)

adr_py_calc = (revenue_py / sold_nights_py) if sold_nights_py > 0 else 0.0
adr_py_col  = _first_mean(df_prev, ["adr","ADR"])
adr_py      = adr_py_calc if adr_py_calc > 0 else (adr_py_col or 0.0)

# --- RevPAR: prima formula (Revenue / Camere disponibili), altrimenti media colonna se disponibile
revpar_calc    = (revenue / rooms_avail)       if rooms_avail    > 0 else 0.0
revpar_col     = _first_mean(df_cur,  ["revpar","RevPAR"])
revpar         = revpar_calc if revpar_calc > 0 else (revpar_col or 0.0)

revpar_py_calc = (revenue_py / rooms_avail_py) if rooms_avail_py > 0 else 0.0
revpar_py_col  = _first_mean(df_prev, ["revpar","RevPAR"])
revpar_py      = revpar_py_calc if revpar_py_calc > 0 else (revpar_py_col or 0.0)

# Occupazione
occ_pct    = (sold_nights    / rooms_avail    * 100.0) if rooms_avail    > 0 else 0.0
occ_pct_py = (sold_nights_py / rooms_avail_py * 100.0) if rooms_avail_py > 0 else 0.0

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
# GRIGLIA 5 COLONNE COERENTE (riutilizzata da header e KPI)
# -----------------------------------------------------------------------------
def _five_slots():
    """Unica griglia condivisa: [2,1,3,1,2] con gap large. Garantisce allineamento 1:1 tra righe."""
    return st.columns([2, 1, 3, 1, 2], gap="large")

def render_year_header_1547(year_label: int):
    """
    Header ANNO: titolo centrato e pulsanti SX/DX.
    Ritorna: {"prev_clicked": bool, "next_clicked": bool}
    """
    col_l, col_c, col_r = st.columns([1,3,1])
    with col_l:
        prev_clicked = st.button("◀", key="year_prev_btn", use_container_width=True)
    with col_c:
        st.markdown(
            f"""
            <div style="text-align:center; line-height:1.05;">
                <div style="font-size:22px; font-weight:700; color:#065f46;">
                    Anno {year_label}
                </div>
                <div style="font-size:14px; font-weight:600; color:#065f46;">
                    (anno di comparazione: {year_label-1})
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_r:
        next_clicked = st.button("▶", key="year_next_btn", use_container_width=True)

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

    # -----------------------------------------------------------------------------
# STRISCIA ANNO – KPI (stessa grafica/struttura della striscia MESE)
# -----------------------------------------------------------------------------
def _compute_year_kpis(df_all_like: pd.DataFrame, year: int) -> tuple[dict, dict]:
    """Calcola KPI annuali + delta YoY sullo stesso perimetro di strutture selezionate."""
    df_y  = df_all_like[df_all_like["year"] == year].copy()
    df_py = df_all_like[df_all_like["year"] == year - 1].copy()

    # --- helper robusti su colonne possibili ---
    def _sum_first(df: pd.DataFrame, cands: list[str]) -> float:
        if df is None or df.empty: return 0.0
        for c in cands:
            if c in df.columns:
                try: return float(df[c].sum())
                except: pass
        return 0.0

    def _mean_first(df: pd.DataFrame, cands: list[str]) -> float:
        if df is None or df.empty: return 0.0
        for c in cands:
            if c in df.columns:
                try: return float(df[c].mean())
                except: pass
        return 0.0

    # Fallback camere disponibili anno (se mancano rooms_available nel file)
    def _fallback_rooms_avail_year(df_year_like: pd.DataFrame, default_rooms: int) -> float:
        if df_year_like is None or df_year_like.empty: return 0.0
        tot = 0.0
        props = df_year_like["property"].dropna().unique().tolist() if "property" in df_year_like.columns else [None]
        for p in props:
            dfp = df_year_like if p is None else df_year_like[df_year_like["property"] == p]
            rooms = int(ROOMS_MAP.get(p, default_rooms)) if p is not None else int(default_rooms)
            for _, r in dfp[["year", "month"]].drop_duplicates().iterrows():
                tot += rooms * calendar.monthrange(int(r["year"]), int(r["month"]))[1]
        return float(tot)

    # --- KPI anno corrente ---
    sold_y   = int(_sum_first(df_y,  ["occupied","sold_nights","rooms_sold","nights","notti"]))
    rooms_y  = _sum_first(df_y, ["rooms_available","rooms_avail","camere_disponibili"]) or _fallback_rooms_avail_year(df_y, ROOMS_DEFAULT)
    rev_y    = _sum_first(df_y,  ["revenue","totale_revenue","ricavi"])
    adr_y    = _mean_first(df_y, ["adr"])
    rpar_y   = _mean_first(df_y, ["revpar"])
    occ_y    = (sold_y / rooms_y * 100.0) if rooms_y > 0 else 0.0

    # --- KPI anno precedente (per delta YoY) ---
    sold_py  = int(_sum_first(df_py,  ["occupied","sold_nights","rooms_sold","nights","notti"]))
    rooms_py = _sum_first(df_py, ["rooms_available","rooms_avail","camere_disponibili"]) or _fallback_rooms_avail_year(df_py, ROOMS_DEFAULT)
    rev_py   = _sum_first(df_py,  ["revenue","totale_revenue","ricavi"])
    adr_py   = _mean_first(df_py, ["adr"])
    rpar_py  = _mean_first(df_py, ["revpar"])
    occ_py   = (sold_py / rooms_py * 100.0) if rooms_py > 0 else 0.0

    # --- formattazioni coerenti con la striscia mese ---
    def _fmt_eur(x: float) -> str:
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{CURRENCY} {s}"

    def _fmt_pct(x: float) -> str:
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s}%"

    def _fmt_th(n: int) -> str:
        return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

    kpi_year = {
        "Revenue":      _fmt_eur(rev_y),
        "Occupazione":  _fmt_pct(occ_y),
        "Notti vendute":_fmt_th(sold_y),
        "ADR":          _fmt_eur(adr_y),
        "RevPAR":       _fmt_eur(rpar_y),
    }
    deltas_year = {
        "Revenue":       rev_y  - rev_py,
        "Occupazione":   occ_y  - occ_py,
        "Notti vendute": sold_y - sold_py,
        "ADR":           adr_y  - adr_py,
        "RevPAR":        rpar_y - rpar_py,
    }
    return kpi_year, deltas_year


def render_year_kpis_1547(kpi: dict, deltas: dict):
    """UI della striscia dati ANNO – identica alla striscia dati MESE (stesse classi, stessi layout)."""
    # Stessi stili della striscia mese (li includiamo anche qui perché la barra anno è renderizzata prima)
    st.markdown("""
<style>
.kpi-col{ width:100%; display:flex; flex-direction:column; align-items:center; }
.kpi-label{ font-size:14px; color:#6b7280; margin-bottom:6px; white-space:nowrap; }
.kpi-value{ font-size:36px; font-weight:400; color:#111827; line-height:1.15; white-space:nowrap; } /* no bold */
.kpi-pill{ display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px;
           font-size:13px; font-weight:600; margin-top:8px; }
.kpi-pill.up{ background:#ecfdf5; color:#16a34a; }
.kpi-pill.down{ background:#fef2f2; color:#dc2626; }
</style>
""", unsafe_allow_html=True)

    def pill(delta: float) -> str:
        if delta is None: return ""
        cls  = "up" if delta >= 0 else "down"
        icon = "↑" if delta >= 0 else "↓"
        val  = f"{delta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span class="kpi-pill {cls}">{icon} {val}</span>'

    # Identica griglia: [2,1,3,1,2]
    col_rev, col_occ, col_notti, col_adr, col_rpar = _five_slots()

    with col_rev:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Revenue anno</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Revenue","–")}</div>{pill(deltas.get("Revenue"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_occ:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Occupazione</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Occupazione","–")}</div>{pill(deltas.get("Occupazione"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_notti:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Notti vendute</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Notti vendute","–")}</div>{pill(deltas.get("Notti vendute"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_adr:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">ADR medio</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("ADR","–")}</div>{pill(deltas.get("ADR"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_rpar:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">RevPAR medio</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("RevPAR","–")}</div>{pill(deltas.get("RevPAR"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    """Navigazione ANNO su 5 colonne, identica alla barra mese."""
    prev_year = year_label - 1
    next_year = year_label + 1

    # usa la stessa griglia condivisa
    c1, c2, c3, c4, c5 = _five_slots()

    # SX: pulsante + label anno precedente (verde scuro bold)
    with c1:
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        prev_clicked = st.button("◀", key="yh_prev", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{prev_year}</div>', unsafe_allow_html=True)

       # CENTRO: anno corrente (grande, centrato anche verticalmente) + sottotitolo identico alla barra mese
    with c3:
        compare_year = year_label - 1
        st.markdown(
            f'''
<div class="mh-center" style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:110px;">
  <p class="mh-month" style="font-size:28px; line-height:1.1; font-weight:700;">Anno {year_label}</p>
  <div class="mh-sub">(anno di comparazione: {compare_year})</div>
</div>
''',
            unsafe_allow_html=True
        )

    # DX: pulsante + label anno successivo (verde scuro bold)
    with c5:
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        next_clicked = st.button("▶", key="yh_next", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{next_year}</div>', unsafe_allow_html=True)

    st.divider()
    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# -----------------------------------------------------------------------------
# STRISCIA MESE – Navigazione (5 colonne)
# -----------------------------------------------------------------------------
def render_month_header_1547(month_label: str, prev_month_label: str, next_month_label: str, compare_year: int):
    c1, c2, c3, c4, c5 = _five_slots()

    with c1:  # pulsante sinistro + label mese precedente
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        prev_clicked = st.button("◀", key="mh_prev", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#166534; font-weight:700;">{prev_month_label}</div>', unsafe_allow_html=True)

    with c3:
        st.markdown(
        f'''
        <div class="mh-center" style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:110px;">
        <p class="mh-month" style="font-size:28px; line-height:1.1; font-weight:700;">{month_label}</p>
        <div class="mh-sub">(anno di comparazione: {compare_year})</div>
        </div>
        ''',
        unsafe_allow_html=True
    )

    with c5:  # pulsante destro + label mese successivo
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        next_clicked = st.button("▶", key="mh_next", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#166534; font-weight:700;">{next_month_label}</div>', unsafe_allow_html=True)

    st.divider()
    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# -----------------------------------------------------------------------------
# STRISCIA MESE – KPI (5 colonne allineate all’header)
# -----------------------------------------------------------------------------
def render_month_kpis_1547(kpi: dict[str, str], deltas: dict[str, float]):
    # --- CSS grid a 5 colonne fisse: 2fr 1fr 3fr 1fr 2fr ---
    st.markdown("""
<style>
.kpi-row {
  display: grid;
  grid-template-columns: 2fr 1fr 3fr 1fr 2fr;
  column-gap: 64px;        /* allinea al gap "large" dell'header */
  align-items: start;
}
.kpi-box {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;   /* centra il contenuto nel proprio slot */
}
.kpi-label { font-size: 14px; color: #6b7280; margin-bottom: 6px; white-space: nowrap; }
.kpi-value { font-size: 36px; font-weight: 400; color: #111827; line-height: 1.15; white-space: nowrap; }
.kpi-pill  { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 999px;
             font-size: 13px; font-weight: 600; margin-top: 8px; }
.kpi-pill.up   { background: #ecfdf5; color: #16a34a; }
.kpi-pill.down { background: #fef2f2; color: #dc2626; }
</style>
""", unsafe_allow_html=True)

    # helper per la pill del delta
    def pill(delta: float) -> str:
        if delta is None:
            return ""
        is_up = delta >= 0
        cls = "up" if is_up else "down"
        icon = "↑" if is_up else "↓"
        val = f"{delta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span class="kpi-pill {cls}">{icon} {val}</span>'

    # HTML della riga KPI: 5 celle -> 1) Revenue  2) Occupazione  3) Notti vendute  4) ADR  5) RevPAR
    html = f"""
<div class="kpi-row">
  <div class="kpi-box">
    <div class="kpi-label">Revenue mese</div>
    <div class="kpi-value">{kpi.get("Revenue","–")}</div>
    {pill(deltas.get("Revenue"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">Occupazione</div>
    <div class="kpi-value">{kpi.get("Occupazione","–")}</div>
    {pill(deltas.get("Occupazione"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">Notti vendute</div>
    <div class="kpi-value">{kpi.get("Notti vendute","–")}</div>
    {pill(deltas.get("Notti vendute"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">ADR medio</div>
    <div class="kpi-value">{kpi.get("ADR","–")}</div>
    {pill(deltas.get("ADR"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">RevPAR medio</div>
    <div class="kpi-value">{kpi.get("RevPAR","–")}</div>
    {pill(deltas.get("RevPAR"))}
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    st.divider()
    
# -----------------------------------------------------------------------------
# RENDER PAGINA
# -----------------------------------------------------------------------------
# === NAVIGAZIONE ANNO (prima della sezione mese) ===
yhdr = render_year_header_1547(active_y)

# Cambio anno: aggiorna anche il mese alla mensilità corrente del calendario, mantenendo lo stesso anno interrogato
if yhdr.get("prev_clicked"):
    st.session_state["active_year"] = active_y - 1
    st.session_state["active_month"] = datetime.now().month   # mese corrente, ma del nuovo anno
    st.rerun()
if yhdr.get("next_clicked"):
    st.session_state["active_year"] = active_y + 1
    st.session_state["active_month"] = datetime.now().month   # mese corrente, ma del nuovo anno
    st.rerun()
    
# === STRISCIA DATI – ANNO (riuso del renderer MESE per allineamento pixel-perfect) ===
kpi_year, deltas_year = _compute_year_kpis(df_view, active_y)
render_month_kpis_1547(kpi_year, deltas_year)

with c2:
    st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-label">Occupazione anno</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">{kpi_year["Occupazione anno"]}</div>{_pill_html("Occupazione anno", delta_year_raw["Occupazione anno"])}', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-label">Notti vendute anno</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">{kpi_year["Notti vendute anno"]}</div>{_pill_html("Notti vendute anno", delta_year_raw["Notti vendute anno"])}', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c4:
    st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-label">ADR medio anno</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">{kpi_year["ADR medio anno"]}</div>{_pill_html("ADR medio anno", delta_year_raw["ADR medio anno"])}', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with c5:
    st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
    st.markdown('<div class="kpi-label">RevPAR medio anno</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi-value">{kpi_year["RevPAR medio anno"]}</div>{_pill_html("RevPAR medio anno", delta_year_raw["RevPAR medio anno"])}', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

hdr = render_month_header_1547(
    month_label=curr_label,
    prev_month_label=prev_label,
    next_month_label=next_label,
    compare_year=active_y - 1
)
if hdr.get("prev_clicked"): go_prev(); st.rerun()
if hdr.get("next_clicked"): go_next(); st.rerun()

render_month_kpis_1547(kpi_header, deltas_header)

# -----------------------------------------------------------------------------
# (segue tutto il resto della pagina: KPI mensili, tabelle, grafici…)
# -----------------------------------------------------------------------------
