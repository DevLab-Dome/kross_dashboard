# forecast_ingest.py
# Indicizzazione robusta dei file forecast archiviati per PROPERTY/DATE.
# Legge dalla cartella montata via env FORECAST_DIR (default: /data/forecasts).
# Output: lista dei file validi con (property, snapshot_date, file_path, file_name, size_bytes, mtime).

from __future__ import annotations
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

DEFAULT_BASE = os.getenv("FORECAST_DIR", "/data/forecasts")
DATE_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD

SUPPORTED_EXT = {".xlsx", ".xls"}  # estensioni supportate

@dataclass(frozen=True)
class ForecastFile:
    property: str
    snapshot_date: datetime
    file_path: str
    file_name: str
    size_bytes: int
    mtime: datetime

def _is_date_folder(name: str) -> bool:
    return bool(DATE_RX.match(name))

def _safe_datetime(dt: float) -> datetime:
    try:
        return datetime.fromtimestamp(dt)
    except Exception:
        return datetime.utcfromtimestamp(0)

def _norm_property(name: str) -> str:
    # Manteniamo il nome cartella (Lavagnini, La_Terrazza, …) come "chiave property".
    return name

def list_properties(base_dir: str = DEFAULT_BASE) -> List[str]:
    if not os.path.isdir(base_dir):
        return []
    props = []
    for entry in os.listdir(base_dir):
        path = os.path.join(base_dir, entry)
        if os.path.isdir(path) and entry not in {"inbox"}:
            props.append(entry)
    return sorted(props)

def scan_forecast_catalog(base_dir: str = DEFAULT_BASE) -> List[ForecastFile]:
    """
    Scansiona /<BASE>/<PROPERTY>/<YYYY-MM-DD>/*.xlsx
    Ignora folder 'inbox' e date non conformi.
    """
    catalog: List[ForecastFile] = []
    if not os.path.isdir(base_dir):
        return catalog

    for prop in list_properties(base_dir):
        prop_dir = os.path.join(base_dir, prop)
        for date_folder in os.listdir(prop_dir):
            if date_folder == "inbox":
                continue
            if not _is_date_folder(date_folder):
                continue
            snap_dir = os.path.join(prop_dir, date_folder)
            if not os.path.isdir(snap_dir):
                continue

            # parse data
            try:
                snap_dt = datetime.strptime(date_folder, "%Y-%m-%d")
            except ValueError:
                continue

            for fname in os.listdir(snap_dir):
                fpath = os.path.join(snap_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in SUPPORTED_EXT:
                    continue
                try:
                    st = os.stat(fpath)
                    size = int(st.st_size)
                    mtime = _safe_datetime(st.st_mtime)
                except OSError:
                    size = 0
                    mtime = datetime.utcfromtimestamp(0)

                catalog.append(
                    ForecastFile(
                        property=_norm_property(prop),
                        snapshot_date=snap_dt,
                        file_path=fpath,
                        file_name=fname,
                        size_bytes=size,
                        mtime=mtime,
                    )
                )
    # Ordina dal più recente al più vecchio
    catalog.sort(key=lambda x: (x.property.lower(), x.snapshot_date, x.file_name.lower()))
    return catalog

def latest_snapshot_per_property(base_dir: str = DEFAULT_BASE) -> List[ForecastFile]:
    """
    Restituisce l'ultimo file (per data più recente) per ciascuna property.
    Se nella stessa data ci sono più file, prende quello alfabeticamente ultimo (tipico se ci sono versioni).
    """
    catalog = scan_forecast_catalog(base_dir)
    out: List[ForecastFile] = []
    cur_prop: Optional[str] = None
    cur_date: Optional[datetime] = None
    cur_file: Optional[ForecastFile] = None

    for item in catalog:
        if item.property != cur_prop:
            # flush precedente
            if cur_file is not None:
                out.append(cur_file)
            # reset
            cur_prop = item.property
            cur_date = item.snapshot_date
            cur_file = item
            continue

        # stessa property
        if item.snapshot_date > (cur_date or datetime.min):
            cur_date = item.snapshot_date
            cur_file = item
        elif item.snapshot_date == cur_date and cur_file and item.file_name > cur_file.file_name:
            # stessa data: scegliamo l'ultimo per nome (grezzo ma deterministico)
            cur_file = item

    if cur_file is not None:
        out.append(cur_file)
    return out

# Helpers per integrazione Streamlit (senza importare streamlit qui dentro)
def as_rows(files: List[ForecastFile]) -> List[dict]:
    return [
        {
            "property": f.property,
            "snapshot_date": f.snapshot_date.strftime("%Y-%m-%d"),
            "file_name": f.file_name,
            "file_path": f.file_path,
            "size_kb": round(f.size_bytes / 1024.0, 1),
            "mtime": f.mtime.isoformat(timespec="seconds"),
        }
        for f in files
    ]
