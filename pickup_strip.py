# pickup_strip.py
# Sezione "Pick-up — Prossimi 11 mesi" richiamabile dalla home (streamlit_app).
# Mostra KPI aggregati per i prossimi 11 mesi usando l'ultimo snapshot disponibile.
# Dipendenze: forecast_ingest.py, forecast_parser_kross.py

import os
from datetime import datetime, date
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from forecast_ingest import (
    scan_forecast_catalog,
    DEFAULT_BASE,
    as_rows,
)
from forecast_parser_kross import parse_kross_excel

BASE_DIR = os.getenv("FORECAST_DIR", DEFAULT_BASE)

@st.cache_data(ttl=300)
def _catalog_df(base_dir: str) -> pd.DataFrame:
    files = scan_forecast_catalog(base_dir)
    return pd.DataFrame(as_rows(files))

@st.cache_data(ttl=300)
def _parse_snapshot(path: str, prop: str, snap_date: datetime) -> pd.DataFrame:
    df, _ = parse_kross_excel(path, property_name=prop, snapshot_date=snap_date)
    # tipi
    df["stay_date"] = pd.to_datetime(df["stay_date"]).dt.date
    for c in ["rooms_sold", "revenue_total", "adr", "revpar"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _last_snapshot_path_for(prop: str, df_catalog: pd.DataFrame) -> Tuple[Optional[str], Optional[date]]:
    q = df_catalog[df_catalog["property"] == prop]
    if q.empty:
        return None, None
    q = q.sort_values(["snapshot_date", "file_name"]).tail(1)
    fpath = q.iloc[0]["file_path"]
    snap_date = pd.to_datetime(q.iloc[0]["snapshot_date"]).date()
    return fpath, snap_date

def render_pickup_next_11_months(prop: str, ref_date: Optional[date] = None) -> None:
    """
    Renderizza la strip 'Prossimi 11 mesi' con KPI (Revenue, Rooms, ADR, RevPAR) aggregati per mese di soggiorno.
    - prop: nome property (cartella storage)
    - ref_date: data "oggi"; default = oggi (Europe/Rome lato server)
    """
    df_catalog = _catalog_df(BASE_DIR)

    # guard contro catalogo vuoto/strutturato
    if df_catalog is None or df_catalog.empty or "property" not in df_catalog.columns:
        st.markdown("### Pick-up — Prossimi 11 mesi")
        st.info("Nessuno snapshot indicizzato. Carica i file in `/srv/ihosp/forecasts/<PROPERTY>/inbox/` "
                "e attendi l'archiviazione notturna, poi ricarica la pagina.")
        return

    st.markdown("### Pick-up — Prossimi 11 mesi")

    fpath, snap_date = _last_snapshot_path_for(prop, df_catalog)
    if not fpath or not snap_date:
        st.info("Nessuno snapshot archiviato per questa property.")
        return

    today = ref_date or date.today()
    df = _parse_snapshot(fpath, prop, datetime.combine(snap_date, datetime.min.time()))

    # Finestra: da oggi (incluso) fino a +11 mesi (fine mese)
    start = pd.to_datetime(today)
    end = (start + pd.DateOffset(months=11)).to_period("M").end_time
    mask = (pd.to_datetime(df["stay_date"]) >= start) & (pd.to_datetime(df["stay_date"]) <= end)
    win = df.loc[mask].copy()

    if win.empty:
        st.warning("Nessun dato di soggiorno nei prossimi 11 mesi nello snapshot corrente.")
        return

    # Aggregazione per mese di soggiorno
    win["month"] = pd.to_datetime(win["stay_date"]).dt.to_period("M").astype(str)
    agg = win.groupby("month", as_index=False).agg(
        revenue_total=("revenue_total", "sum"),
        rooms_sold=("rooms_sold", "sum"),
        adr=("adr", "mean"),
        revpar=("revpar", "mean"),
    ).sort_values("month")

    # KPI headline (sommatoria 11 mesi)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Revenue (11 mesi)", f"€ {agg['revenue_total'].sum():,.2f}".replace(",", "."))
    col2.metric("Notti vendute (11 mesi)", f"{int(agg['rooms_sold'].sum())}")
    col3.metric("ADR medio", f"€ {agg['adr'].mean():.2f}")
    col4.metric("RevPAR medio", f"€ {agg['revpar'].mean():.2f}")

    # Tabella mensile
    table = agg.rename(columns={
        "month": "Mese",
        "revenue_total": "Revenue",
        "rooms_sold": "Notti vendute",
        "adr": "ADR medio",
        "revpar": "RevPAR medio"
    })
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.caption(f"Snapshot usato: {snap_date} · File: `{os.path.basename(fpath)}` · "
               f"Finestra: {start.date()} → {end.date()}")
