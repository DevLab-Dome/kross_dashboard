# forecast_parser_kross.py
# Parser robusto per export Kross (IT) con fallback CSV.
# Output standard:
#   [property, snapshot_date, stay_date, rooms_sold, revenue_total, adr, revpar]

from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from zipfile import BadZipFile

# -------------------- MAPPING COLONNE (case-insensitive) ---------------------

COLUMN_ALIASES: Dict[str, list] = {
    "stay_date": ["data", "giorno", "date"],
    "rooms_sold": ["occupate", "camere occupate", "rooms sold"],
    "revenue_total": ["totale revenue", "revenue", "ricavi totali"],
    "adr": ["adr"],
    "revpar": ["revpar", "rev par"],
}

def _norm(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s.translate(str.maketrans("àèéìòóù", "aeeioou"))

def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    norm_map = {_norm(c): c for c in df.columns}
    resolved: Dict[str, str] = {}
    for key, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            n = _norm(alias)
            if n in norm_map:
                resolved[key] = norm_map[n]
                break
    return resolved

# -------------------------- DATACLASS DI SUPPORTO ----------------------------

@dataclass(frozen=True)
class ParsedInfo:
    property: str
    snapshot_date: Optional[datetime]
    rows: int
    source_path: str

# --------------------------------- HELPERS -----------------------------------

def _empty_frame(property_name: str, snapshot_date: Optional[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=["property", "snapshot_date", "stay_date", "rooms_sold", "revenue_total", "adr", "revpar"]
    )

def _to_date(s: pd.Series) -> pd.Series:
    def _one(x: Any):
        if pd.isna(x):
            return np.nan
        if isinstance(x, (pd.Timestamp, datetime)):
            return x.date()
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            dt = pd.to_datetime(x, unit="D", origin="1899-12-30", errors="coerce")
            return dt.date() if not pd.isna(dt) else np.nan
        xs = str(x).strip()
        dt = pd.to_datetime(xs, errors="coerce", dayfirst=False)
        if pd.isna(dt):
            dt = pd.to_datetime(xs, errors="coerce", dayfirst=True)
        return dt.date() if not pd.isna(dt) else np.nan
    return s.map(_one)

def _to_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        r = a / b
    return r.replace([np.inf, -np.inf], np.nan)

# ------------------------------ FUNZIONE MAIN --------------------------------

def parse_kross_excel(
    file_path: str,
    property_name: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    sheet_name: Optional[str] = None,
) -> Tuple[pd.DataFrame, ParsedInfo]:
    """
    Legge un export Kross (.xlsx reale o CSV mascherato) e restituisce colonne canoniche:
      [property, snapshot_date, stay_date, rooms_sold, revenue_total, adr, revpar]
    Fallback CSV automatico se il file .xlsx non è un vero Excel.
    """

    # --- inferenze dal path ---
    if property_name is None:
        parts = os.path.normpath(file_path).split(os.sep)
        prop = None
        for i, p in enumerate(parts):
            if p == "inbox" and i > 0:
                prop = parts[i - 1]
                break
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p) and i > 0:
                prop = parts[i - 1]
                break
        property_name = prop or "UNKNOWN"

    if snapshot_date is None:
        snap = None
        for p in os.path.normpath(file_path).split(os.sep):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
                try:
                    snap = datetime.strptime(p, "%Y-%m-%d")
                    break
                except Exception:
                    pass
        snapshot_date = snap  # può restare None

    # --- lettura tabella con fallback CSV ---
    raw = None
    try:
        xl = pd.ExcelFile(file_path, engine="openpyxl")
        sh = sheet_name or (xl.sheet_names[0] if xl.sheet_names else None)
        if sh is None:
            raise ValueError(f"Nessun foglio trovato in: {file_path}")
        raw = xl.parse(sh)
    except (BadZipFile, ValueError, FileNotFoundError):
        try:
            raw = pd.read_csv(file_path, sep=None, engine="python")  # autodetect
        except Exception:
            try:
                raw = pd.read_csv(file_path, sep=";")
            except Exception as e:
                raise ValueError(f"Impossibile leggere il file come Excel o CSV: {file_path} — {e}")

    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return _empty_frame(property_name, snapshot_date), ParsedInfo(property_name, snapshot_date, 0, file_path)

    # --- mapping colonne ---
    colmap = _match_columns(raw)
    req = {"stay_date", "rooms_sold", "revenue_total"}
    if not req.issubset(colmap.keys()):
        missing = req - set(colmap.keys())
        raise ValueError(f"Colonne obbligatorie mancanti in {file_path}: {missing} — trovate: {list(raw.columns)}")

    # --- normalizzazione dati ---
    df = pd.DataFrame()
    df["stay_date"] = _to_date(raw[colmap["stay_date"]])
    df["rooms_sold"] = _to_numeric(raw[colmap["rooms_sold"]])
    df["revenue_total"] = _to_numeric(raw[colmap["revenue_total"]])

    if "adr" in colmap:
        df["adr"] = _to_numeric(raw[colmap["adr"]])
    else:
        df["adr"] = _safe_div(df["revenue_total"], df["rooms_sold"])

    if "revpar" in colmap:
        df["revpar"] = _to_numeric(raw[colmap["revpar"]])
    else:
        df["revpar"] = np.nan

    df["property"] = property_name
    df["snapshot_date"] = snapshot_date.date().isoformat() if snapshot_date else None

    df = df[~df["stay_date"].isna()].copy()
    df = df.sort_values("stay_date").reset_index(drop=True)

    info = ParsedInfo(property=property_name, snapshot_date=snapshot_date, rows=len(df), source_path=file_path)
    return df[["property", "snapshot_date", "stay_date", "rooms_sold", "revenue_total", "adr", "revpar"]], info
