
"""
Pick-up Engine — DevLab (Hospitality)
-------------------------------------
Calcola le variazioni OTB (oggi vs ieri, vs data scelta) sui KPI aggregati
per property × (anno, mese di soggiorno), usando gli snapshot salvati in
SQLite da `otb_snapshots.py`.

Output pronto per UI "Striscia Pick-up — MESE/ANNO" e tabelle di dettaglio.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date

KPI_FIELDS = ["revenue","nights_sold","rooms_available","occupancy_pct","adr","revpar"]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers DB
# ─────────────────────────────────────────────────────────────────────────────
def _connect(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path))

def _load_as_of(conn: sqlite3.Connection, as_of: date | str, property_name: Optional[str]) -> pd.DataFrame:
    as_of = pd.to_datetime(as_of).date().isoformat()
    if property_name:
        q = "SELECT * FROM otb_monthly_snapshots WHERE as_of_date=? AND property=?"
        return pd.read_sql_query(q, conn, params=[as_of, property_name])
    else:
        q = "SELECT * FROM otb_monthly_snapshots WHERE as_of_date=?"
        return pd.read_sql_query(q, conn, params=[as_of])

def _latest_before(conn: sqlite3.Connection, as_of: date | str) -> Optional[str]:
    as_of = pd.to_datetime(as_of).date().isoformat()
    q = "SELECT MAX(as_of_date) FROM otb_monthly_snapshots WHERE as_of_date < ?"
    row = conn.execute(q, [as_of]).fetchone()
    return row[0] if row and row[0] else None

# ─────────────────────────────────────────────────────────────────────────────
# Core: pick-up tra due date
# ─────────────────────────────────────────────────────────────────────────────
def pickup_between(db_path: str | Path, as_of_current: date | str, as_of_prev: Optional[date | str] = None,
                   property_name: Optional[str] = None) -> pd.DataFrame:
    """
    Ritorna un DF con:
      property, stay_year, stay_month,
      <kpi>_cur, <kpi>_prev, <kpi>_delta, <kpi>_delta_pct
    Se as_of_prev è None, usa l'ultimo snapshot disponibile prima di as_of_current.
    """
    with _connect(db_path) as conn:
        cur_df = _load_as_of(conn, as_of_current, property_name)
        if as_of_prev is None:
            prev_date = _latest_before(conn, as_of_current)
            if not prev_date:
                # nessun confronto possibile
                base = cur_df.copy()
                for k in KPI_FIELDS:
                    base[f"{k}_cur"] = pd.to_numeric(base[k], errors="coerce").fillna(0.0)
                    base[f"{k}_prev"] = 0.0
                    base[f"{k}_delta"] = base[f"{k}_cur"]
                    base[f"{k}_delta_pct"] = np.where(base[f"{k}_cur"]!=0, 100.0, 0.0)
                keep = ["property","stay_year","stay_month"] +                            [f"{k}_{sfx}" for k in KPI_FIELDS for sfx in ("cur","prev","delta","delta_pct")]
                return base.reindex(columns=keep).fillna(0.0)
            as_of_prev = prev_date
        prev_df = _load_as_of(conn, as_of_prev, property_name)

    # Se non ci sono righe per il prev, tratta come zero
    # Facciamo merge full outer su property, year, month
    key = ["property","stay_year","stay_month"]
    cur = cur_df[key + KPI_FIELDS].copy()
    prev = prev_df[key + KPI_FIELDS].copy()
    for df in (cur, prev):
        for k in KPI_FIELDS:
            df[k] = pd.to_numeric(df[k], errors="coerce").fillna(0.0)

    merged = pd.merge(cur, prev, on=key, how="outer", suffixes=("_cur_raw","_prev_raw")).fillna(0.0)

    # Calcolo delta e %
    for k in KPI_FIELDS:
        merged[f"{k}_cur"] = merged[f"{k}_cur_raw"]
        merged[f"{k}_prev"] = merged[f"{k}_prev_raw"]
        merged[f"{k}_delta"] = merged[f"{k}_cur"] - merged[f"{k}_prev"]
        # Per percentuali: se prev=0 e cur!=0 → 100% pickup; se entrambi 0 → 0%
        denom = merged[f"{k}_prev"].replace(0, np.nan)
        merged[f"{k}_delta_pct"] = np.where(
            denom.notna(), (merged[f"{k}_delta"] / denom) * 100.0,
            np.where(merged[f"{k}_cur"] != 0, 100.0, 0.0)
        )

    keep = key + [f"{k}_{sfx}" for k in KPI_FIELDS for sfx in ("cur","prev","delta","delta_pct")]
    return merged.reindex(columns=keep)

# ─────────────────────────────────────────────────────────────────────────────
# Utilità per aggregare a livello ANNO (somma o media coerente)
# ─────────────────────────────────────────────────────────────────────────────
def pickup_yearly(df_month_level: pd.DataFrame) -> pd.DataFrame:
    """
    Aggrega il risultato mensile a livello ANNO con le regole:
     - Revenue, nights_sold, rooms_available: SOMMA dei delta/valori
     - ADR, RevPAR, Occupancy: media ponderata sui giorni coperti non è possibile qui
       (mancano i pesi in output); usiamo media semplice come proxy per il pickup.
    """
    if df_month_level.empty:
        return df_month_level

    out = df_month_level.copy()
    out["stay_year"] = out["stay_year"].astype(int)

    def _agg_rules(prefix: str):
        return {
            f"{prefix}_cur": "sum",
            f"{prefix}_prev": "sum",
            f"{prefix}_delta": "sum",
            f"{prefix}_delta_pct": "mean",
        }

    grp = out.groupby(["property","stay_year"], as_index=False).agg({
        **_agg_rules("revenue"),
        **_agg_rules("nights_sold"),
        **_agg_rules("rooms_available"),
        **_agg_rules("occupancy_pct"),
        **_agg_rules("adr"),
        **_agg_rules("revpar"),
    })
    return grp

# ─────────────────────────────────────────────────────────────────────────────
# CLI di comodo
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="DevLab Pick-up Engine (oggi vs ieri)")
    ap.add_argument("--db", required=True, help="Path SQLite DB")
    ap.add_argument("--as-of", required=True, help="As-of corrente (YYYY-MM-DD)")
    ap.add_argument("--prev", default=None, help="As-of di confronto (default: ultimo snapshot precedente)")
    ap.add_argument("--property", default=None, help="Filtra una singola property")
    ap.add_argument("--level", choices=["month","year"], default="month", help="Livello output")
    args = ap.parse_args()

    df = pickup_between(args.db, args.as_of, args.prev, args.property)
    if args.level == "year":
        df = pickup_yearly(df)

    # Stampa un estratto ordinato per anno/mese
    sort_cols = ["property","stay_year"] + (["stay_month"] if "stay_month" in df.columns else [])
    df = df.sort_values(sort_cols)
    pd.set_option("display.max_columns", None)
    print(df.head(100).to_string(index=False))
