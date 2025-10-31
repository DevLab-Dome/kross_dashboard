# pages/10_PickUp_Catalogo.py
# UI di sola indicizzazione: elenca lo storico dei file Forecast archiviati
# e mostra l'ultimo snapshot per ciascuna property.
# Legge da FORECAST_DIR (montato nel container come /data/forecasts).

from __future__ import annotations
import os
from datetime import datetime
import pandas as pd
import streamlit as st

from forecast_ingest import (
    scan_forecast_catalog,
    latest_snapshot_per_property,
    as_rows,
    list_properties,
    DEFAULT_BASE,
)

st.set_page_config(page_title="Pick-Up · Catalogo", page_icon="📦", layout="wide")

BASE_DIR = os.getenv("FORECAST_DIR", DEFAULT_BASE)

@st.cache_data(ttl=300)
def load_catalog(base_dir: str):
    files = scan_forecast_catalog(base_dir)
    return pd.DataFrame(as_rows(files))

@st.cache_data(ttl=300)
def load_latest(base_dir: str):
    latest = latest_snapshot_per_property(base_dir)
    return pd.DataFrame(as_rows(latest))

st.title("📦 Pick-Up — Catalogo Forecast")
st.caption(f"Archivio base: `{BASE_DIR}` (solo lettura) · refresh ogni 5 minuti")

# Pannello filtri
col_f1, col_f2, col_f3 = st.columns([1,1,2], gap="small")
with col_f1:
    props = ["Tutte"] + list_properties(BASE_DIR)
    sel_prop = st.selectbox("Property", props, index=0)
with col_f2:
    sort_mode = st.selectbox("Ordina per", ["Data crescente", "Data decrescente"], index=1)

df = load_catalog(BASE_DIR)

if df.empty:
    st.info("Nessun file indicizzato. Carica i file giornalieri nelle cartelle **inbox** su VPS; lo scheduler li archivierà automaticamente per data.")
else:
    # Filtro property
    if sel_prop != "Tutte":
        df = df[df["property"] == sel_prop]

    # Ordinamento
    if sort_mode == "Data crescente":
        df = df.sort_values(["property", "snapshot_date", "file_name"], ascending=[True, True, True])
    else:
        df = df.sort_values(["property", "snapshot_date", "file_name"], ascending=[True, False, True])

    st.subheader("📑 Storico file indicizzati")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "property": "Property",
            "snapshot_date": "Snapshot",
            "file_name": "File",
            "file_path": st.column_config.Column("Percorso", help="Percorso assoluto nel container"),
            "size_kb": st.column_config.NumberColumn("Dimensione (KB)", format="%.1f"),
            "mtime": "Ultima modifica",
        },
    )

    st.divider()

    st.subheader("🏁 Ultimo snapshot per Property")
    df_latest = load_latest(BASE_DIR)
    st.dataframe(
        df_latest.sort_values("property"),
        use_container_width=True,
        hide_index=True,
        column_config={
            "property": "Property",
            "snapshot_date": "Snapshot",
            "file_name": "File",
            "size_kb": st.column_config.NumberColumn("KB", format="%.1f"),
        },
    )

st.caption(
    "Operativa: carica i nuovi forecast del giorno in `/srv/ihosp/forecasts/<PROPERTY>/inbox/`. "
    "Lo scheduler notturno li archivia in `/srv/ihosp/forecasts/<PROPERTY>/<YYYY-MM-DD>/`."
)
