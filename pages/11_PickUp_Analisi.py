# pages/11_PickUp_Analisi.py
# Analisi Pick-Up: calcolo Δ su D-1 / D-3 / D-7 tra snapshot storici.
# Legge i file indicizzati da forecast_ingest e li parsea con forecast_parser_kross.

from __future__ import annotations
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

from forecast_ingest import (
    scan_forecast_catalog,
    latest_snapshot_per_property,
    list_properties,
    DEFAULT_BASE,
    as_rows,
)
from forecast_parser_kross import parse_kross_excel

st.set_page_config(page_title="Pick-Up · Analisi", page_icon="📈", layout="wide")

BASE_DIR = os.getenv("FORECAST_DIR", DEFAULT_BASE)

# ---------- Helpers -----------------------------------------------------------

@st.cache_data(ttl=300)
def _catalog_df(base_dir: str) -> pd.DataFrame:
    return pd.DataFrame(as_rows(scan_forecast_catalog(base_dir)))

def _get_snapshot_file_for(prop: str, snap_date: datetime, df_catalog: pd.DataFrame) -> str | None:
    q = df_catalog[(df_catalog["property"] == prop) & (df_catalog["snapshot_date"] == snap_date.strftime("%Y-%m-%d"))]
    if q.empty:
        return None
    # se più file nella stessa data: prendi l'ultimo per nome
    q = q.sort_values("file_name").tail(1)
    return q.iloc[0]["file_path"]

@st.cache_data(ttl=300)
def _parse_snapshot(path: str, prop: str, snap_date: datetime) -> pd.DataFrame:
    df, _info = parse_kross_excel(path, property_name=prop, snapshot_date=snap_date)
    # garantisce i tipi
    df["stay_date"] = pd.to_datetime(df["stay_date"]).dt.date
    for c in ["rooms_sold", "revenue_total", "adr", "revpar"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _pickup_delta(df_now: pd.DataFrame, df_prev: pd.DataFrame) -> pd.DataFrame:
    # merge per stay_date
    now = df_now.rename(columns={
        "rooms_sold": "rooms_now",
        "revenue_total": "revenue_now",
        "adr": "adr_now",
        "revpar": "revpar_now",
    })[["stay_date","rooms_now","revenue_now","adr_now","revpar_now"]]

    prev = df_prev.rename(columns={
        "rooms_sold": "rooms_prev",
        "revenue_total": "revenue_prev",
        "adr": "adr_prev",
        "revpar": "revpar_prev",
    })[["stay_date","rooms_prev","revenue_prev","adr_prev","revpar_prev"]]

    m = pd.merge(now, prev, on="stay_date", how="outer")
    # delta elementari
    m["Δ_rooms"]   = (m["rooms_now"]   - m["rooms_prev"]).fillna(0)
    m["Δ_revenue"] = (m["revenue_now"] - m["revenue_prev"]).fillna(0)
    # ADR delta: differenza tra medie giornaliere (non weighted qui)
    m["Δ_adr"]     = (m["adr_now"]     - m["adr_prev"])
    # ordina per data soggiorno
    m = m.sort_values("stay_date")
    return m

def _summary_monthly(m: pd.DataFrame) -> pd.DataFrame:
    if m.empty:
        return m
    mm = m.copy()
    mm["month"] = pd.to_datetime(mm["stay_date"]).dt.to_period("M").astype(str)
    out = mm.groupby("month", as_index=False).agg({
        "Δ_rooms": "sum",
        "Δ_revenue": "sum",
        "Δ_adr": "mean",   # media semplice dei delta ADR per il mese
    })
    return out.sort_values("month")

# ---------- UI ----------------------------------------------------------------

st.title("📈 Pick-Up — Analisi (D-1 / D-3 / D-7)")
st.caption(f"Archivio forecast: `{BASE_DIR}` · i calcoli usano gli snapshot storici già archiviati")

props = list_properties(BASE_DIR)
if not props:
    st.info("Nessuna property trovata. Carica file in `/srv/ihosp/forecasts/<PROPERTY>/inbox/`.")
    st.stop()

col1, col2, col3 = st.columns([1,1,2], gap="small")
with col1:
    prop = st.selectbox("Property", props, index=0)

df_catalog = _catalog_df(BASE_DIR)

# Date disponibili per la property scelta
snap_dates = sorted(pd.to_datetime(df_catalog[df_catalog["property"] == prop]["snapshot_date"].unique()).date)
if not snap_dates:
    st.info(f"Nessuno snapshot per **{prop}**. Carica almeno 2 giorni per vedere D-1/D-3/D-7.")
    st.stop()

with col2:
    # snapshot corrente = ultimo disponibile
    snap_now = max(snap_dates)
    st.write(f"Snapshot corrente: **{snap_now}**")
with col3:
    st.write("")

st.divider()

def _render_block(label: str, offset_days: int):
    st.subheader(f"{label} (oggi vs {offset_days} giorni fa)")
    prev_date = snap_now - timedelta(days=offset_days)

    # trova il file per la data esatta; se manca, fallback al più recente precedente
    file_now = _get_snapshot_file_for(prop, datetime.combine(snap_now, datetime.min.time()), df_catalog)
    file_prev = _get_snapshot_file_for(prop, datetime.combine(prev_date, datetime.min.time()), df_catalog)

    # fallback: cerca il più recente <= prev_date
    if file_prev is None:
        prev_candidates = [d for d in snap_dates if d <= prev_date]
        if prev_candidates:
            prev_date = max(prev_candidates)
            file_prev = _get_snapshot_file_for(prop, datetime.combine(prev_date, datetime.min.time()), df_catalog)

    if not file_now or not file_prev:
        st.warning(f"Snapshot mancante per il confronto {label}. Servono almeno due scatti (oggi e {offset_days} giorni prima).")
        return

    # parse
    df_now  = _parse_snapshot(file_now,  prop, datetime.combine(snap_now,  datetime.min.time()))
    df_prev = _parse_snapshot(file_prev, prop, datetime.combine(prev_date, datetime.min.time()))

    # calcolo delta per ogni data di soggiorno
    m = _pickup_delta(df_now, df_prev)

    # KPI riassuntivi totali (sull’intero orizzonte del file)
    kpi_cols = st.columns(3)
    kpi_cols[0].metric("Δ Rooms",   f"{int(m['Δ_rooms'].sum())}")
    kpi_cols[1].metric("Δ Revenue", f"{m['Δ_revenue'].sum():,.0f}".replace(",", "."))  # formato italiano semplice
    kpi_cols[2].metric("Δ ADR (media)", f"{m['Δ_adr'].mean():.2f}")

    # Tabella giornaliera
    st.markdown("**Dettaglio per data di soggiorno**")
    st.dataframe(
        m[["stay_date","rooms_now","rooms_prev","Δ_rooms","revenue_now","revenue_prev","Δ_revenue","adr_now","adr_prev","Δ_adr"]],
        use_container_width=True,
        hide_index=True,
    )

    # Aggregazione mensile
    st.markdown("**Sintesi per mese di soggiorno**")
    mm = _summary_monthly(m)
    st.dataframe(mm, use_container_width=True, hide_index=True)

# Blocchi D-1 / D-3 / D-7
for label, offset in [("D-1", 1), ("D-3", 3), ("D-7", 7)]:
    _render_block(label, offset)
    st.divider()
