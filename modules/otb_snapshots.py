
"""
OTB Snapshot Engine — DevLab (Hospitality)
------------------------------------------
Scopo: salvare snapshot giornalieri del forecast (as_of_date) aggregati per
property × (anno, mese di soggiorno), per abilitare confronti Oggi vs Ieri, 7gg,
STLY ecc. Nessun aggancio UI in questo file.

Standard calcoli (DevLab):
  • Revenue (mese) = somma "Totale revenue"
  • Notti vendute (mese) = somma delle notti/occupied
  • Occupazione (mese, %) = notti_vendute / camere_disponibili × 100
  • ADR (mese) = media giornaliera ADR
  • RevPAR (mese) = media giornaliera RevPAR

Nota: se il file non contiene "rooms_available", è comunque possibile salvare
revenue, notti, ADR, RevPAR. L'occupazione sarà 0 finché non verrà fornito il
dato o una mappa camere_nominali × giorni_del_mese lato app.
"""
from __future__ import annotations
import hashlib
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, datetime
import calendar

# ─────────────────────────────────────────────────────────────────────────────
# Schema SQLite
# ─────────────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS otb_monthly_snapshots (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of_date       TEXT    NOT NULL,                         -- 'YYYY-MM-DD' (data del caricamento)
    property         TEXT    NOT NULL,                         -- nome struttura
    stay_year        INTEGER NOT NULL,
    stay_month       INTEGER NOT NULL,                         -- 1..12 (mese di soggiorno)
    revenue          REAL    NOT NULL DEFAULT 0,
    nights_sold      REAL    NOT NULL DEFAULT 0,               -- notti/rooms_sold
    rooms_available  REAL    NOT NULL DEFAULT 0,
    occupancy_pct    REAL    NOT NULL DEFAULT 0,               -- 0..100
    adr              REAL    NOT NULL DEFAULT 0,
    revpar           REAL    NOT NULL DEFAULT 0,
    rows_covered     INTEGER NOT NULL DEFAULT 0,               -- # giorni inclusi nell'aggregazione
    source_name      TEXT    NOT NULL,                         -- nome file di origine
    source_hash      TEXT    NOT NULL,                         -- hash per dedup
    created_at       TEXT    NOT NULL                          -- timestamp inserimento
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_snapshot
  ON otb_monthly_snapshots(property, as_of_date, stay_year, stay_month);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Normalizzazione colonne e aggregazione
# ─────────────────────────────────────────────────────────────────────────────
# Candidati colonne (accetta formati diversi)
COLMAP = {
    "date":        ["date", "giorno", "data", "stay_date", "arrivo", "ds"],
    "revenue":     ["totale_revenue", "revenue", "ricavi", "tot_revenue"],
    "nights":      ["occupied", "sold_nights", "rooms_sold", "notti", "nights"],
    "rooms_avail": ["rooms_available", "rooms_avail", "camere_disponibili", "capacity"],
    "adr":         ["adr", "avg_daily_rate", "tariffa_media"],
    "revpar":      ["revpar", "rev_par"],
    "property":    ["property", "struttura", "hotel", "house_name"]
}

def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _hash_df(df: pd.DataFrame) -> str:
    # Hash sulla rappresentazione CSV ordinata per stabilità (limitando le dimensioni)
    sample = df.sort_index(axis=1).to_csv(index=False).encode("utf-8")
    return hashlib.sha256(sample).hexdigest()

def normalize_forecast(df: pd.DataFrame, property_name: str | None = None) -> pd.DataFrame:
    """Ritorna DF normalizzato con colonne canoniche: date, revenue, nights, rooms_avail, adr, revpar, property."""
    df = df.copy()
    # Individua colonne
    c_date  = _first_existing(df, COLMAP["date"])
    if c_date is None:
        raise ValueError("Colonna data non trovata (attesi: %s)" % COLMAP["date"])
    df["date"] = pd.to_datetime(df[c_date]).dt.date

    def _ensure(colkey: str, default: float = 0.0):
        cname = _first_existing(df, COLMAP[colkey])
        if cname is None:
            df[colkey] = default
        else:
            df[colkey] = pd.to_numeric(df[cname], errors="coerce").fillna(0.0)

    _ensure("revenue", 0.0)
    _ensure("nights", 0.0)
    _ensure("rooms_avail", 0.0)
    _ensure("adr", 0.0)
    _ensure("revpar", 0.0)

    if property_name is None:
        c_prop = _first_existing(df, COLMAP["property"])
        if c_prop is None:
            df["property"] = "UNKNOWN"
        else:
            df["property"] = df[c_prop].astype(str)
    else:
        df["property"] = str(property_name)

    # Aggiunge campi anno/mese di soggiorno
    df["stay_year"]  = pd.to_datetime(df["date"]).dt.year
    df["stay_month"] = pd.to_datetime(df["date"]).dt.month
    return df[["property","date","stay_year","stay_month","revenue","nights","rooms_avail","adr","revpar"]]

def aggregate_monthly(df_norm: pd.DataFrame) -> pd.DataFrame:
    """Aggrega per property × anno × mese secondo standard DevLab."""
    if df_norm.empty:
        return df_norm.assign(rows_covered=0)

    grp = df_norm.groupby(["property","stay_year","stay_month"], as_index=False)
    agg = grp.agg({
        "revenue": "sum",
        "nights": "sum",
        "rooms_avail": "sum",
        "adr": "mean",         # media giornaliera ADR
        "revpar": "mean",      # media giornaliera RevPAR
        "date": "nunique"      # giorni coperti
    }).rename(columns={"date":"rows_covered"})

    # Occupazione = notti / camere_disponibili × 100
    agg["occupancy_pct"] = np.where(agg["rooms_avail"] > 0,
                                    (agg["nights"] / agg["rooms_avail"]) * 100.0,
                                    0.0)
    return agg

# ─────────────────────────────────────────────────────────────────────────────
# DB Helpers
# ─────────────────────────────────────────────────────────────────────────────
def init_db(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.executescript(SCHEMA_SQL)
    return conn

def insert_snapshot_rows(conn: sqlite3.Connection, as_of: date, source_name: str, source_hash: str, agg_monthly: pd.DataFrame) -> int:
    """Inserisce righe (UPSERT su chiave unica). Ritorna #righe inserite/aggiornate."""
    if agg_monthly.empty:
        return 0
    rows = []
    ts = datetime.utcnow().isoformat(timespec="seconds")
    for _, r in agg_monthly.iterrows():
        rows.append((
            as_of.isoformat(),
            str(r["property"]),
            int(r["stay_year"]),
            int(r["stay_month"]),
            float(r["revenue"]),
            float(r["nights"]),
            float(r["rooms_avail"]),
            float(r["occupancy_pct"]),
            float(r["adr"]),
            float(r["revpar"]),
            int(r["rows_covered"]),
            source_name,
            source_hash,
            ts
        ))
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO otb_monthly_snapshots
        (as_of_date, property, stay_year, stay_month, revenue, nights_sold, rooms_available,
         occupancy_pct, adr, revpar, rows_covered, source_name, source_hash, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(property, as_of_date, stay_year, stay_month) DO UPDATE SET
            revenue         = excluded.revenue,
            nights_sold     = excluded.nights_sold,
            rooms_available = excluded.rooms_available,
            occupancy_pct   = excluded.occupancy_pct,
            adr             = excluded.adr,
            revpar          = excluded.revpar,
            rows_covered    = excluded.rows_covered,
            source_name     = excluded.source_name,
            source_hash     = excluded.source_hash,
            created_at      = excluded.created_at
        ;
    """, rows)
    conn.commit()
    return cur.rowcount

# ─────────────────────────────────────────────────────────────────────────────
# API principale
# ─────────────────────────────────────────────────────────────────────────────
def ingest_forecast_file(db_path: str | Path, file_path: str | Path, as_of: date | str, property_name: str | None = None,
                         sheet: str | int | None = 0, skiprows: int = 0) -> int:
    """
    Legge un file Forecast (Excel/CSV), normalizza, aggrega e salva snapshot OTB mensile.
    - db_path: path al file SQLite (es: '.devlab/data/snapshots.db')
    - file_path: path al forecast da importare (giornaliero con righe per data soggiorno)
    - as_of: data della fotografia (giorno in cui importi)
    - property_name: opzionale (se il file non ha colonna property)
    - sheet: per Excel, nome/indice del foglio (default=0)
    - skiprows: righe iniziali da saltare
    Ritorna #righe inserite/aggiornate.
    """
    as_of = pd.to_datetime(as_of).date()
    file_path = Path(file_path)
    src_name = file_path.name

    # Carica
    if file_path.suffix.lower() in [".xls", ".xlsx", ".xlsm"]:
        df = pd.read_excel(file_path, sheet_name=sheet, skiprows=skiprows)
    elif file_path.suffix.lower() in [".csv", ".txt"]:
        df = pd.read_csv(file_path)
    else:
        raise ValueError(f"Formato non supportato: {file_path.suffix}")

    src_hash = _hash_df(df)
    df_norm = normalize_forecast(df, property_name=property_name)
    agg = aggregate_monthly(df_norm)

    conn = init_db(db_path)
    try:
        n = insert_snapshot_rows(conn, as_of=as_of, source_name=src_name, source_hash=src_hash, agg_monthly=agg)
    finally:
        conn.close()
    return n

# ─────────────────────────────────────────────────────────────────────────────
# Query utili per il Pick-up Engine (step successivo)
# ─────────────────────────────────────────────────────────────────────────────
def load_snapshot(conn: sqlite3.Connection, as_of: date | str, property_name: str | None = None) -> pd.DataFrame:
    as_of = pd.to_datetime(as_of).date().isoformat()
    if property_name:
        q = "SELECT * FROM otb_monthly_snapshots WHERE as_of_date=? AND property=?"
        return pd.read_sql_query(q, conn, params=[as_of, property_name])
    else:
        q = "SELECT * FROM otb_monthly_snapshots WHERE as_of_date=?"
        return pd.read_sql_query(q, conn, params=[as_of])

def list_as_of_dates(conn: sqlite3.Connection) -> list[str]:
    q = "SELECT DISTINCT as_of_date FROM otb_monthly_snapshots ORDER BY as_of_date DESC"
    rows = conn.execute(q).fetchall()
    return [r[0] for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# CLI di comodo: python otb_snapshots.py --db snapshots.db --as-of 2025-10-28 --file forecast.xlsx --property "Hotel"
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    ap = argparse.ArgumentParser(description="DevLab OTB Snapshot Engine")
    ap.add_argument("--db", required=True, help="Path SQLite DB (es: .devlab/data/snapshots.db)")
    ap.add_argument("--as-of", required=True, help="Data fotografia (YYYY-MM-DD)")
    ap.add_argument("--file", required=True, nargs="+", help="Uno o più file forecast (Excel/CSV)")
    ap.add_argument("--property", default=None, help="Nome property (se manca nel file)")
    ap.add_argument("--sheet", default=0, help="Nome/indice foglio Excel")
    ap.add_argument("--skiprows", type=int, default=0, help="Righe da saltare all'inizio")
    args = ap.parse_args()

    total = 0
    for f in args.file:
        try:
            n = ingest_forecast_file(args.db, f, args.as_of, property_name=args.property, sheet=args.sheet, skiprows=args.skiprows)
            print(f"[OK] {f}: {n} righe snapshot inserite/aggiornate")
            total += n
        except Exception as e:
            print(f"[ERR] {f}: {e}", file=sys.stderr)
    print(f"Totale righe: {total}")
