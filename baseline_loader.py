# baseline_loader.py
# Lettura baseline/storici per Anno e Mese dalle cartelle montate in BASELINE_DIR
# Struttura attesa:
#   /data/baseline/<PROPERTY>/
#       history_2022.xlsx
#       history_2023.xlsx
#       history_2024.xlsx
#       baseline_2025.xlsx
#       baseline_2026.xlsx
#
# Output normalizzato:
#   [property, year, source, stay_date, rooms_sold, revenue_total, adr, revpar]

from __future__ import annotations
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

BASE_DIR = os.getenv("BASELINE_DIR", "/data/baseline")

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

def _read_table(path: str) -> pd.DataFrame:
    # 1) Excel vero (openpyxl)
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        sh = xl.sheet_names[0]
        df = xl.parse(sh)
        if isinstance(df, pd.DataFrame) and not df.empty:
            return df
    except Exception:
        pass
    # 2) CSV auto
    try:
        return pd.read_csv(path, sep=None, engine="python")
    except Exception:
        pass
    # 3) CSV ';'
    return pd.read_csv(path, sep=";")

@dataclass(frozen=True)
class BaselineFile:
    property: str
    year: int
    source: str   # "history" | "baseline"
    file_path: str

def _infer_meta(prop: str, fname: str) -> Tuple[Optional[int], Optional[str]]:
    f = fname.lower()
    year = None
    src = None
    # history_YYYY.xlsx
    if "history_" in f:
        src = "history"
        try:
            year = int(f.split("history_")[1][:4])
        except Exception:
            year = None
    # baseline_YYYY.xlsx
    if "baseline_" in f:
        src = "baseline"
        try:
            year = int(f.split("baseline_")[1][:4])
        except Exception:
            year = None
    return year, src

def scan_baseline_files(base_dir: str = BASE_DIR) -> List[BaselineFile]:
    out: List[BaselineFile] = []
    if not os.path.isdir(base_dir):
        return out
    for prop in sorted(os.listdir(base_dir)):
        pdir = os.path.join(base_dir, prop)
        if not os.path.isdir(pdir):
            continue
        for fname in os.listdir(pdir):
            if not fname.lower().endswith((".xlsx", ".xls", ".csv")):
                continue
            year, src = _infer_meta(prop, fname)
            if year is None or src is None:
                continue
            out.append(BaselineFile(property=prop, year=year, source=src, file_path=os.path.join(pdir, fname)))
    # ordina per property, year, source (history prima di baseline per coerenza)
    out.sort(key=lambda x: (x.property.lower(), x.year, 0 if x.source == "history" else 1))
    return out

def parse_baseline_file(bf: BaselineFile) -> pd.DataFrame:
    raw = _read_table(bf.file_path)
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=["property","year","source","stay_date","rooms_sold","revenue_total","adr","revpar"])

    colmap = _match_columns(raw)
    req = {"stay_date","rooms_sold","revenue_total"}
    if not req.issubset(colmap.keys()):
        # file non conforme: ritorna df vuoto ma tracciabile
        return pd.DataFrame(columns=["property","year","source","stay_date","rooms_sold","revenue_total","adr","revpar"])

    df = pd.DataFrame()
    df["stay_date"] = _to_date(raw[colmap["stay_date"]])
    df["rooms_sold"] = _to_num(raw[colmap["rooms_sold"]])
    df["revenue_total"] = _to_num(raw[colmap["revenue_total"]])
    # opzionali
    df["adr"] = _to_num(raw[colmap["adr"]]) if "adr" in colmap else (df["revenue_total"] / df["rooms_sold"]).replace([np.inf,-np.inf], np.nan)
    df["revpar"] = _to_num(raw[colmap["revpar"]]) if "revpar" in colmap else np.nan

    df["property"] = bf.property
    df["year"] = int(bf.year)
    df["source"] = bf.source

    df = df[~df["stay_date"].isna()].copy()
    # filtra solo le righe del year dichiarato (per sicurezza)
    df = df[pd.to_datetime(df["stay_date"]).dt.year == df["year"]]
    df = df.sort_values("stay_date").reset_index(drop=True)
    return df[["property","year","source","stay_date","rooms_sold","revenue_total","adr","revpar"]]

# API ad uso streamlit_app -----------------------------------------------------

def load_all_baselines(base_dir: str = BASE_DIR) -> pd.DataFrame:
    """Restituisce un unico DataFrame con tutte le property/anni baseline+history."""
    files = scan_baseline_files(base_dir)
    parts = []
    for bf in files:
        df = parse_baseline_file(bf)
        if not df.empty:
            parts.append(df)
    if not parts:
        return pd.DataFrame(columns=["property","year","source","stay_date","rooms_sold","revenue_total","adr","revpar"])
    out = pd.concat(parts, ignore_index=True)
    # tipi coerenti
    out["stay_date"] = pd.to_datetime(out["stay_date"]).dt.date
    for c in ["rooms_sold","revenue_total","adr","revpar"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def get_year_data(df_all: pd.DataFrame, property_name: str, year: int) -> pd.DataFrame:
    """Filtra i dati per property e anno (history o baseline)."""
    if df_all is None or df_all.empty:
        return df_all
    return df_all[(df_all["property"] == property_name) & (df_all["year"] == int(year))].copy()

def monthly_kpi(df_year: pd.DataFrame) -> pd.DataFrame:
    """Aggrega per mese di soggiorno: Revenue somma, Rooms somma, ADR media, RevPAR media."""
    if df_year is None or df_year.empty:
        return df_year
    d = df_year.copy()
    d["month"] = pd.to_datetime(d["stay_date"]).dt.to_period("M").astype(str)
    agg = d.groupby("month", as_index=False).agg(
        revenue_total=("revenue_total","sum"),
        rooms_sold=("rooms_sold","sum"),
        adr=("adr","mean"),
        revpar=("revpar","mean"),
    ).sort_values("month")
    return agg
