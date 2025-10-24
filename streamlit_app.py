# -*- coding: utf-8 -*-
from __future__ import annotations
from modules.ui_header import render_header_bar
import io, os, calendar
from datetime import datetime
import pandas as pd
import streamlit as st
st.set_page_config(page_title="Kross Dashboard", layout="wide")
"""
# === HEADER DASHBOARD (placeholder; sostituiremo con dati reali nel passo successivo) ===
kpi_values = {
    "Revenue": "€ 0,00",
    "Occupazione": "0,00%",
    "Notti vendute": "0",
    "ADR": "€ 0,00",
    "RevPAR": "€ 0,00",
}
_ = render_header_bar(
    month_label="Ottobre 2025",
    prev_month_label="Settembre",
    next_month_label="Novembre",
    kpi=kpi_values,
    deltas=None,  # es.: {"Revenue": 0.0, "Occupazione": 0.0, "Notti vendute": 0.0, "ADR": 0.0, "RevPAR": 0.0}
    key_prefix="hdr_main",
)
"""
# --- Flag per mostrare/nascondere la sezione "Usa file demo"
try:
    SHOW_DEMO = bool(st.secrets.get("SHOW_DEMO", True))
except Exception:
    SHOW_DEMO = True
import plotly.express as px

from modules.data_loader import load_config, normalize_wide_excel
from modules.metrics import month_overview, next_6_months, filter_by_properties

st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="collapsed")
st.title("DevLab – Kross Dashboard – Multi Struttura")

# ------------------
# CONFIG & STATE
# ------------------
CFG = load_config("config.yaml")
CURRENCY = CFG.get('currency_symbol', '€')
ROOMS_DEFAULT = int(CFG.get('rooms_default', 5))

today = datetime.now()
st.session_state.setdefault('active_year', today.year)
st.session_state.setdefault('active_month', today.month)
# datasets: dict key=(property,year) -> DataFrame
st.session_state.setdefault('datasets', {})

PROPERTIES = ["Lavagnini My Place", "La Terrazza di Jenny"]
YEARS = [2024, 2025]

# ------------------
# SIDEBAR: Selettori + Uploader
# ------------------
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
            try:
                data = upl.read()
                df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
                # opzionale: forziamo filtro anno coerente con selezione
                df = df[df['year'] == year_sel].copy()
                st.session_state['datasets'][(prop_sel, year_sel)] = df
                st.sidebar.success(f"Caricato: {prop_sel} – {year_sel} ({len(df)} righe)")
            except Exception as e:
                st.sidebar.error(f"Errore nel parsing: {e}")

with col_sb_b:
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
                data = f.read()
            try:
                df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
                # taglio all'anno selezionato (gestisce il caso set–dic 2024 per La Terrazza)
                df = df[df['year'] == year_sel].copy()
                st.session_state['datasets'][(prop_sel, year_sel)] = df
                st.sidebar.success(f"Demo caricata: {prop_sel} – {year_sel} ({len(df)} righe)")
            except Exception as e:
                st.sidebar.error(f"Errore demo: {e}")
        else:
            st.sidebar.warning("Demo non disponibile per la combinazione scelta.")

st.sidebar.markdown("---")
if st.sidebar.button("Svuota caricamenti"):
    st.session_state['datasets'].clear()
    st.sidebar.info("Archivio file svuotato.")

# riepilogo caricamenti correnti
if st.session_state['datasets']:
    info_lines = []
    for (p, y), d in sorted(st.session_state['datasets'].items()):
        info_lines.append(f"✅ {p} – {y}")
    st.sidebar.success("\n".join(info_lines))
else:
    st.sidebar.info("Nessun dataset caricato. Seleziona Struttura + Anno, carica un file e premi 'Carica file selezionato'.")

# ------------------
# ASSEMBLA DF GLOBALE
# ------------------
if not st.session_state['datasets']:
    st.warning("Carica almeno un file (Struttura + Anno).")
    st.stop()

df_all = pd.concat(st.session_state['datasets'].values(), ignore_index=True)
properties = sorted(df_all['property'].dropna().unique().tolist())

# ------------------
# VISTA: Singola / Aggregata
# ------------------
st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Vista", options=["Singola struttura", "Aggregata"], index=0)
if view_mode == "Singola struttura":
    prop_view = st.sidebar.selectbox("Seleziona struttura per l'analisi", options=properties, index=0)
    props_to_use = [prop_view]
else:
    props_to_use = st.sidebar.multiselect("Seleziona strutture da aggregare", options=properties, default=properties)

df_view = df_all[df_all['property'].isin(props_to_use)].copy()
if df_view.empty:
    st.warning("Nessun dato per la selezione corrente.")
    st.stop()



# ------------------
# SETUP MESE ATTIVO (ensure vars exist)
# ------------------
active_y = st.session_state['active_year']
active_m = st.session_state['active_month']
mese_nome = calendar.month_name[active_m]
mese_nome = calendar.month_name[active_m]

# ------------------
# NAVIGAZIONE MESE (centered, prev/current/next)
# ------------------
# --- Callback affidabili per la navigazione mese ---
def go_prev():
    m = st.session_state['active_month'] - 1
    y = st.session_state['active_year']
    if m == 0:
        m = 12
        y -= 1
    st.session_state['active_month'] = m
    st.session_state['active_year'] = y

def go_next():
    m = st.session_state['active_month'] + 1
    y = st.session_state['active_year']
    if m == 13:
        m = 1
        y += 1
    st.session_state['active_month'] = m
    st.session_state['active_year'] = y

prev_m = st.session_state['active_month'] - 1
prev_y = st.session_state['active_year']
if prev_m == 0:
    prev_m = 12
    prev_y -= 1
next_m = st.session_state['active_month'] + 1
next_y = st.session_state['active_year']
if next_m == 13:
    next_m = 1
    next_y += 1

prev_label = f"{calendar.month_name[prev_m]} {prev_y}"
curr_label = f"{mese_nome} {active_y}"
next_label = f"{calendar.month_name[next_m]} {next_y}"

bar = st.container()
with bar:
    c_prev, c_curr, c_next = st.columns([1,2,1])
    with c_prev:
        st.write("")
        st.button("◀", key="btn_prev", use_container_width=True, on_click=go_prev)
    with c_curr:
        st.markdown(f"<div style='text-align:center; font-size:1.2rem; font-weight:700'>{curr_label}<br><span style='font-size:0.9rem; font-weight:400'>(anno di comparazione: {active_y-1})</span></div>", unsafe_allow_html=True)
    with c_next:
        st.write("")
        st.button("▶", key="btn_next", use_container_width=True, on_click=go_next)

    c_l, c_c, c_r = st.columns([1,2,1])
    with c_l:
        st.markdown(f"<div style='text-align:center; color:#2c7a7b'>{prev_label}</div>", unsafe_allow_html=True)
    with c_c:
        st.markdown("<div style='text-align:center; opacity:0.0'>.</div>", unsafe_allow_html=True)
    with c_r:
        st.markdown(f"<div style='text-align:center; color:#2c7a7b'>{next_label}</div>", unsafe_allow_html=True)

titolo = f"{curr_label} (vs {active_y-1}) – " + (props_to_use[0] if len(props_to_use)==1 else "Aggregato")
st.markdown("<hr>", unsafe_allow_html=True)


# ------------------
# KPI + YOY
# ------------------
def fmt_currency(x: float) -> str:
    return f"{CURRENCY} {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(x: float) -> str:
    return f"{x:.2f}%"

ov = month_overview(df_view, active_y, active_m, ROOMS_DEFAULT)
curr = ov['curr']; prev = ov['prev']; delta = ov['delta']
# --- ensure numeric deltas (fallback to 0) ---
d_rev = float(delta.get('Δ_revenue', 0) or 0)
d_occ = float(delta.get('Δ_occ_pp', 0) or 0)
d_notti = int(delta.get('Δ_notti', 0) or 0)
d_adr = float(delta.get('Δ_adr', 0) or 0)
d_revpar = float(delta.get('Δ_revpar', 0) or 0)




kpi_cols = st.columns(5)
# Numeric deltas (rounded to 2 decimals for consistent display/color)
d_rev_r = round(d_rev, 2)
d_occ_r = round(d_occ, 2)
d_notti_r = int(d_notti) if isinstance(d_notti, (int, float)) else 0
d_adr_r = round(d_adr, 2)
d_revpar_r = round(d_revpar, 2)

with kpi_cols[0]:
    st.metric("Revenue mese", fmt_currency(curr['revenue']), delta=d_rev_r, delta_color="normal")
with kpi_cols[1]:
    st.metric("Occupazione", fmt_pct(curr['occ_pct']), delta=d_occ_r, delta_color="normal")
with kpi_cols[2]:
    st.metric("Notti vendute", f"{curr['notti']}", delta=d_notti_r, delta_color="normal")
with kpi_cols[3]:
    st.metric("ADR medio", fmt_currency(curr['adr']), delta=d_adr_r, delta_color="normal")
with kpi_cols[4]:
    st.metric("RevPAR medio", fmt_currency(curr['revpar']), delta=d_revpar_r, delta_color="normal")

# Tabella dettaglio YoY con colorazione rossa se valore negativo
def color_span(val_fmt: str, raw_val: float, suffix: str = "") -> str:
    color = "#b60205" if raw_val < 0 else ("#1a7f37" if raw_val > 0 else "inherit")
    return f"<span style='color:{color}; font-weight:600'>{val_fmt}{suffix}</span>"

tbl = pd.DataFrame({
    '': ['Mese corrente', 'Stesso mese anno precedente', 'Δ'],
    'Revenue': [fmt_currency(curr['revenue']), fmt_currency(prev['revenue']), color_span(fmt_currency(d_rev_r), d_rev_r)],
    'Occupazione': [fmt_pct(curr['occ_pct']), fmt_pct(prev['occ_pct']), color_span(f"{d_occ_r:.2f}", d_occ_r, " pp")],
    'Notti': [curr['notti'], prev['notti'], color_span(f"{d_notti_r:+d}", d_notti_r)],
    'ADR': [fmt_currency(curr['adr']), fmt_currency(prev['adr']), color_span(fmt_currency(d_adr_r), d_adr_r)],
    'RevPAR': [fmt_currency(curr['revpar']), fmt_currency(prev['revpar']), color_span(fmt_currency(d_revpar_r), d_revpar_r)],
})
st.markdown(tbl.to_html(index=False, escape=False), unsafe_allow_html=True)


# ------------------
# PROSSIMI 6 MESI
# ------------------
st.markdown("---")
st.subheader("Prossimi 6 mesi – Overview KPI")

df6 = next_6_months(df_view, active_y, active_m, ROOMS_DEFAULT)
# round to 2 decimals for display
df6['revenue_round'] = df6['revenue'].round(2)
df6['adr_round'] = df6['adr'].round(2)
df6['revpar_round'] = df6['revpar'].round(2)
df6['occ_pct_round'] = df6['occ_pct'].round(2)

c1, c2 = st.columns(2)
with c1:
    fig1 = px.bar(df6, x='mese', y='revenue_round', text='revenue_round', title='Revenue per mese (next 6)')
    fig1.update_traces(texttemplate="%{text:.2f}")
    fig1.update_yaxes(tickformat=".2f")
    fig1.update_traces(hovertemplate="Mese %{x}<br>Revenue: %{y:.2f}<extra></extra>")
    st.plotly_chart(fig1, use_container_width=True)
with c2:
    fig2 = px.line(df6, x='mese', y=['occ_pct_round', 'adr_round', 'revpar_round'], title='Occupazione / ADR / RevPAR (next 6)')
    fig2.update_yaxes(tickformat=".2f")
    fig2.update_traces(hovertemplate="Mese %{x}<br>Valore: %{y:.2f}<extra></extra>")
    st.plotly_chart(fig2, use_container_width=True)

st.caption("Formule DevLab: Occupazione = Notti vendute / (Camere nominali × Giorni del mese); "
           "ADR/RevPAR = media giornaliera. Aggregazione: somma per Revenue e Notti; medie per ADR/RevPAR; "
           "Occupazione ricalcolata su camere disponibili del mese.")
