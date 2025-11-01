# pickup_strip.py — versione auto-contenuta (no import parser esterno)
# Mostra "Pick-up — Prossimi 11 mesi" usando l'ULTIMO snapshot disponibile.

import os
from datetime import datetime, date
from typing import Optional, Tuple, Dict, List

import pandas as pd
import numpy as np
import streamlit as st

from forecast_ingest import scan_forecast_catalog, DEFAULT_BASE, as_rows

BASE_DIR = os.getenv("FORECAST_DIR", DEFAULT_BASE)

# ------------------------- utilità lettura file ------------------------------

COLUMN_ALIASES: Dict[str, List[str]] = {
    "stay_date": ["data", "giorno", "date"],
    "rooms_sold": ["occupate", "camere occupate", "rooms sold"],
    "revenue_total": ["totale revenue", "revenue", "ricavi totali"],
    "adr": ["adr"],
    "revpar": ["revpar", "rev par"],
}

def _norm(s: str) -> str:
    s = str(s).strip().lower()
    s = pd.Series([s]).str.normalize("NFKD").str.replace(r"[^\w\s-]", "", regex=True).iloc[0]
    return " ".join(s.split())

def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    norm_map = {_norm(c): c for c in df.columns}
    out: Dict[str, str] = {}
    for key, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            n = _norm(a)
            if n in norm_map:
                out[key] = norm_map[n]
                break
    return out

def _to_date(s: pd.Series) -> pd.Series:
    def _one(x):
        if pd.isna(x): return np.nan
        if isinstance(x, (pd.Timestamp, datetime)): return x.date()
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            dt = pd.to_datetime(x, unit="D", origin="1899-12-30", errors="coerce")
            return dt.date() if not pd.isna(dt) else np.nan
        xs = str(x).strip()
        dt = pd.to_datetime(xs, errors="coerce", dayfirst=False)
        if pd.isna(dt):
            dt = pd.to_datetime(xs, errors="coerce", dayfirst=True)
        return dt.date() if not pd.isna(dt) else np.nan
    return s.map(_one)

def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _read_table(file_path: str) -> pd.DataFrame:
    # 1) vero Excel
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        sh = xl.sheet_names[0]
        df = xl.parse(sh)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    except Exception:
        pass
    # 2) CSV auto separatore
    try:
        return pd.read_csv(file_path, sep=None, engine="python")
    except Exception:
        pass
    # 3) CSV con ';'
    return pd.read_csv(file_path, sep=";")

def _parse_snapshot_table(fpath: str, prop: str, snap_date: datetime) -> pd.DataFrame:
    raw = _read_table(fpath)
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=["property","snapshot_date","stay_date","rooms_sold","revenue_total","adr","revpar"])

    colmap = _match_columns(raw)
    req = {"stay_date","rooms_sold","revenue_total"}
    if not req.issubset(colmap.keys()):
        raise ValueError(f"Colonne mancanti in {os.path.basename(fpath)}; trovate: {list(raw.columns)}")

    df = pd.DataFrame()
    df["stay_date"] = _to_date(raw[colmap["stay_date"]])
    df["rooms_sold"] = _to_num(raw[colmap["rooms_sold"]])
    df["revenue_total"] = _to_num(raw[colmap["revenue_total"]])
    df["adr"] = _to_num(raw[colmap["adr"]]) if "adr" in colmap else (df["revenue_total"] / df["rooms_sold"]).replace([np.inf,-np.inf], np.nan)
    df["revpar"] = _to_num(raw[colmap["revpar"]]) if "revpar" in colmap else np.nan
    df["property"] = prop
    df["snapshot_date"] = snap_date.date().isoformat()
    df = df[~df["stay_date"].isna()].sort_values("stay_date").reset_index(drop=True)
    return df

# ------------------------- catalogo snapshot ---------------------------------

@st.cache_data(ttl=300)
def _catalog_df(base_dir: str) -> pd.DataFrame:
    return pd.DataFrame(as_rows(scan_forecast_catalog(base_dir)))

def _last_snapshot_path_for(prop: str, df_catalog: pd.DataFrame) -> Tuple[Optional[str], Optional[date]]:
    q = df_catalog[df_catalog["property"] == prop]
    if q.empty: return None, None
    q = q.sort_values(["snapshot_date","file_name"]).tail(1)
    return q.iloc[0]["file_path"], pd.to_datetime(q.iloc[0]["snapshot_date"]).date()

@st.cache_data(ttl=300)
def _parse_snapshot(fpath: str, prop: str, snap_date: datetime) -> pd.DataFrame:
    return _parse_snapshot_table(fpath, prop, snap_date)

# --------------------------- render strip ------------------------------------

def render_pickup_next_11_months(prop: str, ref_date: Optional[date] = None) -> None:
    st.markdown("### Pick-up — Prossimi 11 mesi")
    df_catalog = _catalog_df(BASE_DIR)

    if df_catalog is None or df_catalog.empty or "property" not in df_catalog.columns:
        st.info("Nessuno snapshot indicizzato. Carica i file in `/srv/ihosp/forecasts/<PROPERTY>/inbox/` "
                "e attendi l'archiviazione notturna, poi ricarica la pagina.")
        return

    # fallback property se la label non coincide
    catalog_props = sorted(df_catalog["property"].dropna().unique().tolist())
    if prop not in catalog_props:
        low = str(prop).lower()
        guess = None
        for p in catalog_props:
            if p.lower() in low or low in p.lower():
                guess = p; break
        prop = guess or catalog_props[0]
        st.caption(f"(Property selezionata non presente nel catalogo; uso **{prop}**)")

    fpath, snap_d = _last_snapshot_path_for(prop, df_catalog)
    if not fpath or not snap_d:
        st.info("Nessuno snapshot archiviato per questa property.")
        return

    df_now = _parse_snapshot(fpath, prop, datetime.combine(snap_d, datetime.min.time()))

    # finestra prossimi 11 mesi
    today = ref_date or date.today()
    start = pd.to_datetime(today)
    end = (start + pd.DateOffset(months=11)).to_period("M").end_time
    win = df_now[(pd.to_datetime(df_now["stay_date"]) >= start) & (pd.to_datetime(df_now["stay_date"]) <= end)].copy()

    if win.empty:
        st.warning("Nessun dato di soggiorno nei prossimi 11 mesi nello snapshot corrente.")
        return

    win["month"] = pd.to_datetime(win["stay_date"]).dt.to_period("M").astype(str)
    agg = win.groupby("month", as_index=False).agg(
        revenue_total=("revenue_total","sum"),
        rooms_sold=("rooms_sold","sum"),
        adr=("adr","mean"),
        revpar=("revpar","mean"),
    ).sort_values("month")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue (11 mesi)", f"€ {agg['revenue_total'].sum():,.2f}".replace(",", "."))
    c2.metric("Notti vendute (11 mesi)", f"{int(agg['rooms_sold'].sum())}")
    c3.metric("ADR medio", f"€ {agg['adr'].mean():.2f}")
    c4.metric("RevPAR medio", f"€ {agg['revpar'].mean():.2f}")

    table = agg.rename(columns={"month":"Mese","revenue_total":"Revenue","rooms_sold":"Notti vendute","adr":"ADR medio","revpar":"RevPAR medio"})
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.caption(f"Snapshot usato: {snap_d} · File: `{os.path.basename(fpath)}` · Finestra: {start.date()} → {end.date()}")
