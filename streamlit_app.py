# -*- coding: utf-8 -*-
from _future_ import annotations

import io
import os
import calendar
from datetime import datetime

import panda as pd
import plotly.express as px
import streamlit as st

from modules.ui_header import render_header_bar, render_yar_bar
from modules.data_loader import load_config, normalize_wide_excel
from module.metrics import month_overview next_6_months, filter_by_properties

def inject_base_styles():
    st.markdown("""
<style>
:root{
    --dl-font: ui-sans-serif, -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    --dl-muted:#6b7280;
    --dl-fg:#0f172a;
    --dl-accent:#1f6feb;
    --dl-bg:#ffffff;
    --dl-ring:rgba(31,111,235,.25);
    --dl-radius:10px;
    --dl-pad:10px 12px;
    --dl-gap:8px;
    --dl-chip-bg:#f8fafc;
    --dl-chip-fg:#0f172a;
}

/* tipografia generale */
.dl-root, .dl-root *{
    font-family: var(--dl-font);
    letter-spacing: .2px;
}

/* contenitore strip (ANNO/MESE) */
.dl-strip{
    display:flex; align-items:center; gap: var(--dl-gap);
    background: var(--dl-bg); border:1px solid #e5e7eb;
    border-radius: var(--dl-radius); padding: 8px 10px; margin: 6px 0;
}

/* titolo sezione a sinistra */
.dl-title{
    font-weight:600; color:var(--dl-fg); white-space:nowrap;
    padding-right:8px; border-right:1px solid #e5e7eb;
}

/* area bottoni mesi/anni */
.dl-actions{ display:flex; gap:6px; flex-wrap:wrap; }

/* stile coerente per i pulsanti Streamlit */
div.stButton>button{
    padding: var(--dl-pad);
    border-radius: 8px;
    border:1px solid #cbd5e1;
    background:#fff !important;
    color: var(--dl-fg) !important;
    font-weight: 600;
    transition: border-color .12s ease, box-shadow .12s ease;
}
div.stButton>button:hover{ border-color: var(--dl-accent); box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:focus{ outline:none; box-shadow:0 0 0 3px var(--dl-ring); }

/* chip “attivo/selezionato” (mese/anno corrente) */
.dl-chip{
    background: var(--dl-chip-bg);
    color: var(--dl-chip-fg);
    border-radius:999px; padding:4px 10px; font-size:0.9rem; font-weight:600;
}

/* micro-testo secondario */
.dl-hint{ color:var(--dl-muted); font-size:0.85rem; }

/* allineamenti verticali */
.dl-strip{ align-items: center; }
div.stButton{ margin: 0 !important; }
div.stButton > button{
    height: 34px;
    padding: 6px 10px;
    line-height: 20px;
    vertical-align: middle;
}
.dl-actions{ align-items: center; display:flex; flex-wrap:wrap; gap:6px; }

/* stato disabilitato = look chip */
div.stButton > button:disabled{
    background: var(--dl-chip-bg) !important;
    color: var(--dl-chip-fg) !important;
    border-color: #cbd5e1 !important;
    font-weight: 700 !important;
    cursor: default !important;
    opacity: 1 !important;
    box-shadow: none !important;
    pointer-events: none !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# PAGE CONFIG + TITLE
# ---------------------------------------------------------------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="collapsed")
inject_base_styles()
st.markdown('<div class="dl-root"></div>', unsafe_allow_html=True)
st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# ---------------------------------------------------------------------
# CONFIG & STATE
# ---------------------------------------------------------------------
CFG = load_config("config.yaml")
CURRENCY = CFG.get("currency_symbol", "€")
ROOMS_DEFAULT = int(CFG.get("rooms_default", 5))
ROOMS_MAP: dict = CFG.get("rooms_per_property", {})  # mappa camere per struttura

def _fallback_rooms_avail_year(df_year_like: pd.DataFrame, default_rooms: int) -> float:
    """
    Calcola le camere disponibili annue come (camere nominali per struttura × giorni per mese presente nei dati).
    Usa ROOMS_MAP per singola struttura, altrimenti default_rooms.
    """
    if df_year_like is None or df_year_like.empty:
        return 0.0
    total = 0.0
    props = df_year_like["property"].dropna().unique().tolist() if "property" in df_year_like.columns else [None]
    for p in props:
        df_p = df_year_like if p is None else df_year_like[df_year_like["property"] == p]
        rooms_for_p = int(ROOMS_MAP.get(p, default_rooms)) if p is not None else int(default_rooms)
        months = df_p[["year", "month"]].drop_duplicates()
        for _, r in months.iterrows():
            y, m = int(r["year"]), int(r["month"])
            days = calendar.monthrange(y, m)[1]
            total += rooms_for_p * days
    return float(total)

today = datetime.now()
st.session_state.setdefault("active_year", today.year)
st.session_state.setdefault("active_month", today.month)
st.session_state.setdefault("datasets", {})  # dict key=(property,year) -> DataFrame

PROPERTIES = ["Lavagnini My Place", "La Terrazza di Jenny"]
YEARS = [2024, 2025]

# ---------------------------------------------------------------------
# SIDEBAR: Selettori + Uploader
# ---------------------------------------------------------------------
st.sidebar.header("Carica i dati")

prop_sel = st.sidebar.selectbox("Struttura", options=PROPERTIES, index=0)
year_sel = st.sidebar.selectbox(
    "Anno", options=YEARS, index=YEARS.index(today.year) if today.year in YEARS else 0
)

upl = st.sidebar.file_uploader(
    f"File {prop_sel} – {year_sel}", type=["xlsx"], key=f"uploader_{prop_sel}_{year_sel}"
)

col_sb_a, col_sb_b = st.sidebar.columns(2)
with col_sb_a:
    if st.button("Carica file selezionato", use_container_width=True):
        if upl is None:
            st.sidebar.warning("Seleziona un file prima di caricare.")
        else:
            try:
                data = upl.read()
                df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
                df = df[df["year"] == year_sel].copy()
                st.session_state["datasets"][(prop_sel, year_sel)] = df
                st.sidebar.success(f"Caricato: {prop_sel} – {year_sel} ({len(df)} righe)")
            except Exception as e:
                st.sidebar.error(f"Errore nel parsing: {e}")

with col_sb_b:
    SHOW_DEMO = bool(st.secrets.get("SHOW_DEMO", True)) if "SHOW_DEMO" in st.secrets else True
    if SHOW_DEMO and st.button("Usa file demo", use_container_width=True):
        demo_map = {
            ("Lavagnini My Place", 2024): "/mnt/data/Lavagnini_Forecast_01012024_31122024.xlsx",
            ("Lavagnini My Place", 2025): "/mnt/data/Lavagnini_Forecast_01012025_31122025.xlsx",
            ("La Terrazza di Jenny", 2024): "/mnt/data/La_Terrazza_Forecast_01092024_31122024.xlsx",
            ("La Terrazza di Jenny", 2025): "/mnt/data/La_Terrazza_Forecast_01012025_31122025.xlsx",
        }
        path = demo_map.get((prop_sel, year_sel))
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
                df = df[df["year"] == year_sel].copy()
                st.session_state["datasets"][(prop_sel, year_sel)] = df
                st.sidebar.success(f"Demo caricata: {prop_sel} – {year_sel} ({len(df)} righe)")
            except Exception as e:
                st.sidebar.error(f"Errore demo: {e}")
        else:
            st.sidebar.warning("Demo non disponibile per la combinazione scelta.")

st.sidebar.markdown("---")
if st.sidebar.button("Svuota caricamenti"):
    st.session_state["datasets"].clear()
    st.sidebar.info("Archivio file svuotato.")

# riepilogo caricamenti correnti
if st.session_state["datasets"]:
    info_lines = []
    for (p, y), d in sorted(st.session_state["datasets"].items()):
        info_lines.append(f"✅ {p} – {y}")
    st.sidebar.success("\n".join(info_lines))
else:
    st.sidebar.info("Nessun dataset caricato. Seleziona Struttura + Anno, carica un file e premi 'Carica file selezionato'.")

# ---------------------------------------------------------------------
# ASSEMBLA DF GLOBALE
# ---------------------------------------------------------------------
if not st.session_state["datasets"]:
    st.warning("Carica almeno un file (Struttura + Anno).")
    st.stop()

df_all = pd.concat(st.session_state["datasets"].values(), ignore_index=True)
properties = sorted(df_all["property"].dropna().unique().tolist())

# ---------------------------------------------------------------------
# VISTA: Singola / Aggregata
# ---------------------------------------------------------------------
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Vista", options=["Singola struttura", "Aggregata"], index=0)
if view_mode == "Singola struttura":
    prop_view = st.sidebar.selectbox("Seleziona struttura per l'analisi", options=properties, index=0)
    props_to_use = [prop_view]
else:
    props_to_use = st.sidebar.multiselect("Seleziona strutture da aggregare", options=properties, default=properties)

df_view = df_all[df_all["property"].isin(props_to_use)].copy()
if df_view.empty:
    st.warning("Nessun dato per la selezione corrente.")
    st.stop()

# ---------------------------------------------------------------------
# SETUP MESE ATTIVO + NAV
# ---------------------------------------------------------------------
active_y = st.session_state["active_year"]
active_m = st.session_state["active_month"]

def go_prev():
    m = st.session_state["active_month"] - 1
    y = st.session_state["active_year"]
    if m == 0:
        m = 12
        y -= 1
    st.session_state["active_month"] = m
    st.session_state["active_year"] = y

def go_next():
    m = st.session_state["active_month"] + 1
    y = st.session_state["active_year"]
    if m == 13:
        m = 1
        y += 1
    st.session_state["active_month"] = m
    st.session_state["active_year"] = y

prev_m = active_m - 1
prev_y = active_y
if prev_m == 0:
    prev_m = 12
    prev_y -= 1
next_m = active_m + 1
next_y = active_y
if next_m == 13:
    next_m = 1
    next_y += 1

prev_label = f"{calendar.month_name[prev_m]} {prev_y}"
curr_label = f"{calendar.month_name[active_m]} {active_y}"
next_label = f"{calendar.month_name[next_m]} {next_y}"

# ---------------------------------------------------------------------
# KPI MESE CORRENTE (+ YoY) PER HEADER
# ---------------------------------------------------------------------
df_cur = df_view[(df_view["year"] == active_y) & (df_view["month"] == active_m)].copy()
df_prev = df_view[(df_view["year"] == active_y - 1) & (df_view["month"] == active_m)].copy()

def _fmt_thousands(n: int) -> str:
    s = f"{n:,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

def _fmt_eur(x: float) -> str:
    s = f"{x:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY} {s}"

def _fmt_pct(x: float) -> str:
    s = f"{x:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"

sold_nights = int(df_cur["occupied"].sum()) if not df_cur.empty and "occupied" in df_cur.columns else 0
rooms_avail = float(df_cur["rooms_available"].sum()) if not df_cur.empty and "rooms_available" in df_cur.columns else 0.0
revenue     = float(df_cur["revenue"].sum()) if not df_cur.empty and "revenue" in df_cur.columns else 0.0
occ_pct     = (sold_nights / rooms_avail * 100.0) if rooms_avail > 0 else 0.0
adr         = float(df_cur["adr"].mean()) if not df_cur.empty and "adr" in df_cur.columns else 0.0
revpar      = float(df_cur["revpar"].mean()) if not df_cur.empty and "revpar" in df_cur.columns else 0.0

sold_nights_py = int(df_prev["occupied"].sum()) if not df_prev.empty and "occupied" in df_prev.columns else 0
rooms_avail_py = float(df_prev["rooms_available"].sum()) if not df_prev.empty and "rooms_available" in df_prev.columns else 0.0
revenue_py     = float(df_prev["revenue"].sum()) if not df_prev.empty and "revenue" in df_prev.columns else 0.0
occ_pct_py     = (sold_nights_py / rooms_avail_py * 100.0) if rooms_avail_py > 0 else 0.0
adr_py         = float(df_prev["adr"].mean()) if not df_prev.empty and "adr" in df_prev.columns else 0.0
revpar_py      = float(df_prev["revpar"].mean()) if not df_prev.empty and "revpar" in df_prev.columns else 0.0

kpi_header = {
    "Revenue": _fmt_eur(revenue),
    "Occupazione": _fmt_pct(occ_pct),
    "Notti vendute": _fmt_thousands(sold_nights),
    "ADR": _fmt_eur(adr),
    "RevPAR": _fmt_eur(revpar),
}
deltas_header = {
    "Revenue": revenue - revenue_py,
    "Occupazione": occ_pct - occ_pct_py,          # pp
    "Notti vendute": sold_nights - sold_nights_py,
    "ADR": adr - adr_py,
    "RevPAR": revpar - revpar_py,
}

# ---------------------------------------------------------------------
# KPI ANNO CORRENTE (aggregati sull'anno attivo) + YoY
# ---------------------------------------------------------------------
def _sum_first_present(df: pd.DataFrame, candidates: list[str]) -> float:
    if df is None or df.empty:
        return 0.0
    for c in candidates:
        if c in df.columns:
            try:
                return float(df[c].sum())
            except Exception:
                pass
    return 0.0

def _mean_first_present(df: pd.DataFrame, candidates: list[str]) -> float:
    if df is None or df.empty:
        return 0.0
    for c in candidates:
        if c in df.columns:
            try:
                return float(df[c].mean())
            except Exception:
                pass
    return 0.0

df_year    = df_view[df_view["year"] == active_y].copy()
df_year_py = df_view[df_view["year"] == active_y - 1].copy()

NIGHTS_COLS   = ["notti", "nights", "rooms_sold", "sold_nights", "occupied"]
ROOMS_AV_COLS = ["rooms_available", "camere_disponibili", "rooms_avail"]

sold_nights_y    = int(_sum_first_present(df_year, NIGHTS_COLS))
sold_nights_y_py = int(_sum_first_present(df_year_py, NIGHTS_COLS))

rooms_avail_y    = _sum_first_present(df_year, ROOMS_AV_COLS)
rooms_avail_y_py = _sum_first_present(df_year_py, ROOMS_AV_COLS)

if rooms_avail_y == 0.0:
    rooms_avail_y = _fallback_rooms_avail_year(df_year, ROOMS_DEFAULT)
if rooms_avail_y_py == 0.0:
    rooms_avail_y_py = _fallback_rooms_avail_year(df_year_py, ROOMS_DEFAULT)

occ_pct_y    = (sold_nights_y    / rooms_avail_y    * 100.0) if rooms_avail_y    > 0 else 0.0
occ_pct_y_py = (sold_nights_y_py / rooms_avail_y_py * 100.0) if rooms_avail_y_py > 0 else 0.0

revenue_y    = _sum_first_present(df_year,    ["revenue", "ricavi", "totale_revenue"])
revenue_y_py = _sum_first_present(df_year_py, ["revenue", "ricavi", "totale_revenue"])

adr_y       = _mean_first_present(df_year,    ["adr"])
adr_y_py    = _mean_first_present(df_year_py, ["adr"])
revpar_y    = _mean_first_present(df_year,    ["revpar"])
revpar_y_py = _mean_first_present(df_year_py, ["revpar"])

def _fmt_pct2(x: float) -> str:
    return f"{x:.2f}%"

kpi_year = {
    "Revenue": _fmt_eur(revenue_y),
    "Occupazione": _fmt_pct2(occ_pct_y),
    "Notti vendute": _fmt_thousands(sold_nights_y),
    "ADR": _fmt_eur(adr_y),
    "RevPAR": _fmt_eur(revpar_y),
}
deltas_year = {
    "Revenue": revenue_y - revenue_y_py,
    "Occupazione": occ_pct_y - occ_pct_y_py,      # pp
    "Notti vendute": sold_nights_y - sold_nights_y_py,
    "ADR": adr_y - adr_y_py,
    "RevPAR": revpar_y - revpar_y_py,
}

# --- KPI ANNO (titolo vuoto come richiesto) ---
render_year_bar(
    title_html="",
    kpi=kpi_year,
    deltas=deltas_year,
    key_prefix="ybar_main",
)

# ---------------------------------------------------------------------
# STRISCIA MESE (solo pulsanti – wrapper tipografico)
# ---------------------------------------------------------------------
st.markdown('<div class="dl-strip">', unsafe_allow_html=True)
cols = st.columns([1, 5])
with cols[0]:
    st.markdown('<span class="dl-title">MESE</span>', unsafe_allow_html=True)
with cols[1]:
    st.markdown('<div class="dl-actions">', unsafe_allow_html=True)
    res = render_header_bar(
        month_label=curr_label,
        prev_month_label=prev_label,
        next_month_label=next_label,
        kpi=kpi_header,          # ignorato quando show_kpis=False
        deltas=deltas_header,    # idem
        key_prefix="hdr_main",
        show_kpis=False,         # solo pulsanti per la striscia mese
    )
    st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

if res.get("prev_clicked"):
    # NAV MESE PRECEDENTE
    m = st.session_state["active_month"] - 1
    y = st.session_state["active_year"]
    if m == 0:
        m = 12
        y -= 1
    st.session_state["active_month"] = m
    st.session_state["active_year"] = y
    st.rerun()

if res.get("next_clicked"):
    # NAV MESE SUCCESSIVO
    m = st.session_state["active_month"] + 1
    y = st.session_state["active_year"]
    if m == 13:
        m = 1
        y += 1
    st.session_state["active_month"] = m
    st.session_state["active_year"] = y
    st.rerun()

# ---------------------------------------------------------------------
# KPI + YOY DETTAGLIO (tabella)
# ---------------------------------------------------------------------
st.markdown("---")

def fmt_currency(x: float) -> str:
    return f"{CURRENCY} {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(x: float) -> str:
    return f"{x:.2f}%"

ov = month_overview(df_view, active_y, active_m, ROOMS_DEFAULT)
curr = ov["curr"]; prev = ov["prev"]; delta = ov["delta"]

d_rev    = float(delta.get("Δ_revenue", 0) or 0)
d_occ    = float(delta.get("Δ_occ_pp", 0) or 0)
d_notti  = int(delta.get("Δ_notti", 0) or 0)
d_adr    = float(delta.get("Δ_adr", 0) or 0)
d_revpar = float(delta.get("Δ_revpar", 0) or 0)

kpi_cols = st.columns(5)
with kpi_cols[0]:
    st.metric("Revenue mese", fmt_currency(curr["revenue"]), delta=round(d_rev, 2), delta_color="normal")
with kpi_cols[1]:
    st.metric("Occupazione", fmt_pct(curr["occ_pct"]), delta=round(d_occ, 2), delta_color="normal")
with kpi_cols[2]:
    st.metric("Notti vendute", f"{curr['notti']}", delta=int(d_notti), delta_color="normal")
with kpi_cols[3]:
    st.metric("ADR medio", fmt_currency(curr["adr"]), delta=round(d_adr, 2), delta_color="normal")
with kpi_cols[4]:
    st.metric("RevPAR medio", fmt_currency(curr["revpar"]), delta=round(d_revpar, 2), delta_color="normal")

def color_span(val_fmt: str, raw_val: float, suffix: str = "") -> str:
    color = "#b60205" if raw_val < 0 else ("#1a7f37" if raw_val > 0 else "inherit")
    return f"<span style='color:{color}; font-weight:600'>{val_fmt}{suffix}</span>"

tbl = pd.DataFrame({
    "": ["Mese corrente", "Stesso mese anno precedente", "Δ"],
    "Revenue": [fmt_currency(curr["revenue"]), fmt_currency(prev["revenue"]), color_span(fmt_currency(round(d_rev,2)), d_rev)],
    "Occupazione": [fmt_pct(curr["occ_pct"]), fmt_pct(prev["occ_pct"]), color_span(f"{round(d_occ,2):.2f}", d_occ, " pp")],
    "Notti": [curr["notti"], prev["notti"], color_span(f"{int(d_notti):+d}", d_notti)],
    "ADR": [fmt_currency(curr["adr"]), fmt_currency(prev["adr"]), color_span(fmt_currency(round(d_adr,2)), d_adr)],
    "RevPAR": [fmt_currency(curr["revpar"]), fmt_currency(prev["revpar"]), color_span(fmt_currency(round(d_revpar,2)), d_revpar)],
})
st.markdown(tbl.to_html(index=False, escape=False), unsafe_allow_html=True)

# ---------------------------------------------------------------------
# PROSSIMI 6 MESI
# ---------------------------------------------------------------------
st.markdown("---")
st.subheader("Prossimi 6 mesi – Overview KPI")

df6 = next_6_months(df_view, active_y, active_m, ROOMS_DEFAULT)
df6["revenue_round"] = df6["revenue"].round(2)
df6["adr_round"] = df6["adr"].round(2)
df6["revpar_round"] = df6["revpar"].round(2)
df6["occ_pct_round"] = df6["occ_pct"].round(2)

c1, c2 = st.columns(2)
with c1:
    fig1 = px.bar(df6, x="mese", y="revenue_round", text="revenue_round", title="Revenue per mese (next 6)")
    fig1.update_traces(texttemplate="%{text:.2f}")
    fig1.update_yaxes(tickformat=".2f")
    fig1.update_traces(hovertemplate="Mese %{x}<br>Revenue: %{y:.2f}<extra></extra>")
    st.plotly_chart(fig1, use_container_width=True)
with c2:
    fig2 = px.line(df6, x="mese", y=["occ_pct_round", "adr_round", "revpar_round"], title="Occupazione / ADR / RevPAR (next 6)")
    fig2.update_yaxes(tickformat=".2f")
    fig2.update_traces(hovertemplate="Mese %{x}<br>Valore: %{y:.2f}<extra></extra>")
    st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "Formule DevLab: Occupazione = Notti vendute / (Camere nominali × Giorni del mese); "
    "ADR/RevPAR = media giornaliera. Aggregazione: somma per Revenue e Notti; medie per ADR/RevPAR; "
    "Occupazione ricalcolata su camere disponibili del mese."
)
