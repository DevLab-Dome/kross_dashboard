# forecast_parser_kross.py
# Parser robusto per i file Excel esportati da Kross con colonne in italiano.
# Compatibile con il file esempio: unico sheet "Worksheet" e intestazioni:
#  - Data, Unità, Bloccate, Bloccate %, Occupate, Occupate %, Totale revenue, ADR, RevPar, Prenotazioni, ...
#
# Output standardizzato per la dashboard (pick-up e baseline merge):
#  columns: [property, snapshot_date, stay_date, rooms_sold, revenue_total, adr, revpar]
#
# NOTE:
# - mapping case-insensitive e tollerante a spazi/accents
# - conversione data in formato datetime.date
# - coercizione numerica su KPI
# - sheet_name: se non specificato, usa il primo foglio

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from zipfile import BadZipFile

# --- MAPPING COLONNE ---------------------------------------------------------

# chiavi = canonico; valori = lista di possibili intestazioni (case-insensitive)
COLUMN_ALIASES: Dict[str, list[str]] = {
    "stay_date": ["data", "giorno", "date"],
    "rooms_sold": ["occupate", "camere occupate", "rooms sold"],
    "revenue_total": ["totale revenue", "revenue", "ricavi totali"],
    "adr": ["adr"],
    "revpar": ["revpar", "rev par"],
}

# normalizza il nome colonna: minuscolo, spazi compressi, senza accenti
def _norm(s: str) -> str:
    s_low = s.strip().lower()
    s_low = re.sub(r"\s+", " ", s_low)
    # rimuovi accenti comuni
    repl = str.maketrans("àèéìòóù", "aeeioou")
    return s_low.translate(repl)

def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    norm_map = {_norm(c): c for c in df.columns}
    resolved: Dict[str, str] = {}
    for key, aliases in COLUMN_ALIASES.items():
        found = None
        for alias in aliases:
            alias_norm = _norm(alias)
            if alias_norm in norm_map:
                found = norm_map[alias_norm]
                break
        if found:
            resolved[key] = found
    return resolved

# --- DATACLASS DI USCITA (OPZIONALE) -----------------------------------------

@dataclass(frozen=True)
class ParsedInfo:
    property: str
    snapshot_date: Optional[datetime]
    rows: int
    source_path: str

# --- FUNZIONI PRINCIPALI -----------------------------------------------------

def parse_kross_excel(
    file_path: str,
    property_name: Optional[str] = None,
    snapshot_date: Optional[datetime] = None,
    sheet_name: Optional[str] = None,
) -> tuple[pd.DataFrame, ParsedInfo]:
    """
    Legge un file Excel Kross e restituisce un DataFrame con colonne canoniche:
    [property, snapshot_date, stay_date, rooms_sold, revenue_total, adr, revpar]

    Parameters
    ----------
    file_path : str
        Percorso del file .xlsx/.xls
    property_name : Optional[str]
        Nome della property (se None, prova a inferirlo dal path)
    snapshot_date : Optional[datetime]
        Data snapshot (se None, prova a inferirla dal path YYYY-MM-DD)
    sheet_name : Optional[str]
        Nome foglio; se None usa il primo.

    Returns
    -------
    (df, info)
        df : pd.DataFrame (righe valide)
        info: ParsedInfo
    """
    if property_name is None:
        # inferisci dal path: .../<PROPERTY>/<YYYY-MM-DD>/file.xlsx oppure .../<PROPERTY>/inbox/file.xlsx
        parts = os.path.normpath(file_path).split(os.sep)
        # cerca "inbox" o YYYY-MM-DD e prendi la cartella precedente come property
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
        # prova a leggere la directory YYYY-MM-DD nel path
        snap = None
        for p in os.path.normpath(file_path).split(os.sep):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
                try:
                    snap = datetime.strptime(p, "%Y-%m-%d")
                    break
                except Exception:
                    pass
        snapshot_date = snap  # può restare None (inbox)

    # --- lettura tabella con fallback CSV ---
raw = None
try:
    # Tentativo 1: vero Excel (openpyxl)
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    sh = sheet_name or (xl.sheet_names[0] if xl.sheet_names else None)
    if sh is None:
        raise ValueError(f"Nessun foglio trovato in: {file_path}")
    raw = xl.parse(sh)
except (BadZipFile, ValueError, FileNotFoundError):
    # Tentativo 2: CSV (separatore auto, header prima riga)
    try:
        raw = pd.read_csv(file_path, sep=None, engine="python")
    except Exception:
        # Tentativo 3: CSV con separatore ';' (frequente negli export)
        try:
            raw = pd.read_csv(file_path, sep=";")
        except Exception as e:
            raise ValueError(f"Impossibile leggere il file come Excel o CSV: {file_path} — {e}")

# Se ancora vuoto o non DataFrame
if not isinstance(raw, pd.DataFrame) or raw.empty:
    return _empty_frame(property_name, snapshot_date), ParsedInfo(property_name, snapshot_date, 0, file_path)

    # mappa le colonne
    colmap = _match_columns(raw)
    req = {"stay_date", "rooms_sold", "revenue_total"}
    if not req.issubset(colmap.keys()):
        missing = req - set(colmap.keys())
        raise ValueError(f"Colonne obbligatorie mancanti in {file_path}: {missing} — trovate: {list(raw.columns)}")

    df = pd.DataFrame()
    # stay_date
    df["stay_date"] = _to_date(raw[colmap["stay_date"]])
    # numeriche
    df["rooms_sold"] = _to_numeric(raw[colmap["rooms_sold"]])
    df["revenue_total"] = _to_numeric(raw[colmap["revenue_total"]])
    # opzionali
    if "adr" in colmap:
        df["adr"] = _to_numeric(raw[colmap["adr"]])
    else:
        df["adr"] = _safe_div(df["revenue_total"], df["rooms_sold"])
    if "revpar" in colmap:
        df["revpar"] = _to_numeric(raw[colmap["revpar"]])
    else:
        # opzionale: stimabile se servisse, qui lasciamo NaN
        df["revpar"] = np.nan

    # arricchisci con property e snapshot
    df["property"] = property_name
    df["snapshot_date"] = snapshot_date.date().isoformat() if snapshot_date else None

    # filtra righe senza stay_date valide
    df = df[~df["stay_date"].isna()].copy()
    # ordina per data soggiorno
    df = df.sort_values("stay_date").reset_index(drop=True)

    info = ParsedInfo(property=property_name, snapshot_date=snapshot_date, rows=len(df), source_path=file_path)
    return df[["property", "snapshot_date", "stay_date", "rooms_sold", "revenue_total", "adr", "revpar"]], info

# --- HELPERS -----------------------------------------------------------------

def _empty_frame(property_name: str, snapshot_date: Optional[datetime]) -> pd.DataFrame:
    return pd.DataFrame(
        columns=["property", "snapshot_date", "stay_date", "rooms_sold", "revenue_total", "adr", "revpar"]
    )

def _to_date(s: pd.Series) -> pd.Series:
    # accetta str (YYYY-MM-DD o DD/MM/YYYY), datetime, Excel seriali
    def _parse_one(x: Any):
        if pd.isna(x):
            return np.nan
        # già datetime
        if isinstance(x, (pd.Timestamp, datetime)):
            return x.date()
        # numerico (Excel seriale): lascia a pandas
        try:
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                return pd.to_datetime(x, unit="D", origin="1899-12-30", errors="coerce").date()
        except Exception:
            pass
        # stringa
        xs = str(x).strip()
        # tenta ISO
        dt = pd.to_datetime(xs, errors="coerce", dayfirst=False)
        if pd.isna(dt):
            # tenta dayfirst (es. 31/01/2025)
            dt = pd.to_datetime(xs, errors="coerce", dayfirst=True)
        return dt.date() if not pd.isna(dt) else np.nan

    return s.map(_parse_one)

def _to_numeric(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        res = a / b
    return res.replace([np.inf, -np.inf], np.nan)
    
