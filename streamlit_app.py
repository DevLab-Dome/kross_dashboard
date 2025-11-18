# DevLab – Kross Dashboard (STAGING fresh, file unico)
# Invarianti rispettati:
# - Lettura SOLO via HTTP da DigitalOcean Spaces (KROSS_ARCHIVE_URL)
# - Strisce Anno/Mese: i KPI si aggiornano solo coi dati (baseline + forecast)
# - PROD intoccabile: questo file è per STAGING
#
# Baseline:  History_Baseline/<file>.xlsx
# Forecast:  Forecast/<Struttura>/<Anno>/index.json  -> usa files[0] come ultimo forecast
#
# KPI:
# - Occupancy mensile = camere vendute / (camere nominali × giorni del mese)
# - Revenue = somma “Totale revenue”
# - ADR = media giornaliera (Revenue / RoomsSold)
# - RevPAR = media giornaliera (Revenue / Rooms disponibili)
#
# Note:
# - Il forecast NON somma sul totale anno: sostituisce i giorni presenti (delta per override).
# - La "data anchor" del forecast è la PRIMA data nel file forecast (solo informativa in UI).
#
# Dipendenze: streamlit, pandas, requests, openpyxl (lettura xlsx)

import os
from io import BytesIO
from urllib.parse import quote
import json
import requests
import pandas as pd
import streamlit as st

# ---- Config base archivio (HTTP) ----
CDN_BASE = os.environ.get(
    "KROSS_ARCHIVE_URL",
    "https://ihosp-kross-archive.sfo3.cdn.digitaloceanspaces.com"
)

# ---- HTTP helpers ----
def http_get(url: str, timeout: int = 30) -> requests.Response:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r

def read_xlsx_http(url: str) -> pd.DataFrame:
    content = http_get(url).content
    return pd.read_excel(BytesIO(content))

def index_url(structure: str, year: int) -> str:
    # quote con safe='' (nessun carattere lasciato grezzo)
    return f"{CDN_BASE}/Forecast/{quote(structure, safe='')}/{year}/index.json"

def latest_forecast_url(structure: str, year: int):
    try:
        data = http_get(index_url(structure, year)).json()
        files = data.get("files", [])
        return files[0] if files else None
    except Exception:
        return None

# ---- Normalizzazione colonne (robusta, IT friendly) ----
def _normalize_robust(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d.columns = [str(c) for c in d.columns]

    def norm(s):
        return " ".join(str(s).lower().strip().replace("_", " ").replace("-", " ").split())

    cols = {norm(c): c for c in d.columns}

    date_keys  = ["date","data","giorno","data soggiorno","checkin date","arrival date","giornata"]
    sold_keys  = ["roomsold","rooms sold","soldrooms","camere vendute","tot camere vendute","notti vendute","occupied rooms","occupied","vendute","camere occupate"]
    rev_keys   = ["revenue","totalrevenue","total revenue","totale revenue","revenue totale","fatturato","fatturato totale","tot revenue","tot fatturato","totale fatturato"]
    rooms_keys = ["rooms","rooms nominal","roomsnominal","rooms available","roomsavail","capacity","camere","camere nominali","camere disponibili","camere totali"]

    def pick(keys):
        # match esatto normalizzato
        for k in keys:
            if k in cols:
                return cols[k]
        # fallback: substring
        for k in keys:
            for nk, orig in cols.items():
                if k in nk:
                    return orig
        return None

    cdate = pick(date_keys)
    crs   = pick(sold_keys)
    crev  = pick(rev_keys)
    ccap  = pick(rooms_keys)

    if not cdate or not crs or not crev:
        raise ValueError("Colonne indispensabili mancanti (Date/RoomsSold/Revenue)")

    d["Date"]      = pd.to_datetime(d[cdate], dayfirst=True, errors="coerce")
    d["RoomsSold"] = pd.to_numeric(d[crs], errors="coerce").fillna(0.0)
    d["Revenue"]   = pd.to_numeric(d[crev], errors="coerce").fillna(0.0)
    d["Rooms"]     = pd.to_numeric(d[ccap], errors="coerce") if ccap else None

    d = d.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return d[["Date","RoomsSold","Revenue","Rooms"]]

# ---- Delta engine: forecast sovrascrive il baseline solo sulle date presenti ----
def apply_delta(baseline_df: pd.DataFrame, forecast_df: pd.DataFrame | None) -> pd.DataFrame:
    b = _normalize_robust(baseline_df)

    # se mancano le Rooms nella baseline, ripiego su una stima minima (non 0)
    if b["Rooms"].isna().all():
        rs = b["RoomsSold"].max()
        b["Rooms"] = rs if rs > 0 else 1

    if forecast_df is None or forecast_df.empty:
        return recompute_daily(b)

    f = _normalize_robust(forecast_df)
    df = b.merge(f, on="Date", how="outer", suffixes=("_b", "_f")).sort_values("Date")

    # Rooms: usa dove c'è valore, poi forward/backward fill
    df["Rooms"]     = df["Rooms_b"].combine_first(df["Rooms_f"]).ffill().bfill()

    # Override: se forecast ha il valore, usa quello; altrimenti baseline
    df["RoomsSold"] = df["RoomsSold_f"].where(df["RoomsSold_f"].notna(), df["RoomsSold_b"]).fillna(0.0)
    df["Revenue"]   = df["Revenue_f"  ].where(df["Revenue_f"  ].notna(), df["Revenue_b"  ]).fillna(0.0)

    out = df[["Date","RoomsSold","Revenue","Rooms"]].copy()
    if out["Rooms"].isna().all():
        rs = out["RoomsSold"].max()
        out["Rooms"] = rs if rs > 0 else 1

    return recompute_daily(out)

def recompute_daily(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["ADR"]    = (d["Revenue"] / d["RoomsSold"].replace(0, pd.NA)).fillna(0.0)
    d["RevPAR"] = (d["Revenue"] / d["Rooms"].replace(0, pd.NA)).fillna(0.0)
    d["Year"]   = d["Date"].dt.year
    d["Month"]  = d["Date"].dt.month
    return d

def agg_monthly(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(["Year","Month"], as_index=False).agg(
        Revenue=("Revenue","sum"),
        RoomsSold=("RoomsSold","sum"),
        Rooms=("Rooms","sum"),
        Days=("Date","nunique")
    )
    g["ADR"]       = (g["Revenue"] / g["RoomsSold"].replace(0, pd.NA)).fillna(0.0)
    g["RevPAR"]    = (g["Revenue"] / g["Rooms"].replace(0, pd.NA)).fillna(0.0)
    g["Occupancy"] = (g["RoomsSold"] / g["Rooms"].replace(0, pd.NA)).fillna(0.0)
    return g[["Year","Month","Revenue","ADR","RevPAR","Occupancy","RoomsSold","Days"]]

# ---- UI (semplice, “multi struttura”) ----
st.set_page_config(page_title="DevLab – Kross Dashboard (STAGING)", layout="wide", initial_sidebar_state="expanded")
st.title("DevLab – Kross Dashboard — STAGING (HTTP DO Spaces)")
st.caption(f"Archivio: {CDN_BASE}")

st.sidebar.header("Struttura")
STRUCTURES = ["Lavagnini My Place", "La Terrazza di Jenny"]
structure = st.sidebar.selectbox("Seleziona struttura", options=STRUCTURES, index=0)

st.sidebar.header("Anno")
year = st.sidebar.number_input("Anno", min_value=2022, max_value=2030, value=2025, step=1)

st.sidebar.divider()
st.sidebar.header("Sorgenti (HTTP read-only)")
st.sidebar.caption("Baseline: History_Baseline/<file>.xlsx — Forecast: Forecast/<Struttura>/<Anno>/index.json")

# Baseline noti (fotografia): aggiorna/estendi qui se servono altri anni
BASELINE_MAP = {
    "La Terrazza di Jenny": {
        2024: "history_2024_La_Terrazza.xlsx",
        2025: "baseline_2025_La_Terrazza.xlsx",
        2026: "baseline_2026_La_Terrazza.xlsx",
    },
    "Lavagnini My Place": {
        2022: "history_2022_Lavagnini.xlsx",
        2023: "history_2023_Lavagnini.xlsx",
        2024: "history_2024_Lavagnini.xlsx",
        2025: "baseline_2025_Lavagnini.xlsx",
        2026: "baseline_2026_Lavagnini.xlsx",
    },
}

bname = BASELINE_MAP.get(structure, {}).get(int(year))
if not bname:
    st.error("Baseline non definita per questa combinazione Struttura/Anno.")
    st.stop()

baseline_url = f"{CDN_BASE}/History_Baseline/{bname}"
idx_url = index_url(structure, int(year))

st.write("**Baseline:**", bname)
st.code(baseline_url, language="text")
st.write("**Index forecast:**")
st.code(idx_url, language="text")

# ---- Lettura dati ----
try:
    baseline_df = read_xlsx_http(baseline_url)
except Exception as e:
    st.error(f"Errore baseline HTTP: {e}")
    st.stop()

forecast_df = None
fc_url = latest_forecast_url(structure, int(year))
if fc_url:
    st.write("**Ultimo forecast:**", fc_url)
    try:
        forecast_df = read_xlsx_http(fc_url)
    except Exception as e:
        st.warning(f"Forecast non leggibile: {e}")

# ---- Calcolo KPI ----
daily = apply_delta(baseline_df, forecast_df)
monthly = agg_monthly(daily)

# Anchor (prima data del forecast, se presente)
if forecast_df is not None and not forecast_df.empty:
    try:
        # prima data “vera” nel file forecast (colonna 0 dopo normalizzazione semantica)
        tmp = forecast_df.copy()
        # proviamo le chiavi più comuni per sicurezza
        for k in ["Date","Data","giorno","day"]:
            if k in tmp.columns:
                anchor_date = pd.to_datetime(tmp[k], dayfirst=True, errors="coerce").min()
                break
        else:
            anchor_date = pd.NaT
        if pd.notna(anchor_date):
            st.info(f"📌 Forecast anchor (prima data nel file): {anchor_date.date()}")
    except Exception:
        pass

st.subheader("KPI mensili")
st.dataframe(monthly, use_container_width=True)

st.success("STAGING attivo (fresh): HTTP DO Spaces + Delta KPI.")
