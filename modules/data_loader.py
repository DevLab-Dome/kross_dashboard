# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import os
import yaml
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

HEADER_MAP = {
    'data': 'date',
    'unità': 'rooms_total',
    'unita': 'rooms_total',
    'bloccate': 'rooms_blocked',
    'bloccate %': 'rooms_blocked_pct',
    'occupate': 'rooms_sold',
    'occupate %': 'occ_pct',
    'totale revenue': 'revenue',
    'adr': 'adr',
    'revpar': 'revpar',
    'prenotazioni': 'bookings',
    'ospiti': 'guests',
    'adulti': 'adults',
    'bambini': 'children',
    'arrivi (prenotazioni)': 'arrivals_bookings',
    'arrivi (ospiti)': 'arrivals_guests',
    'partenze (prenotazioni)': 'departures_bookings',
    'partenze (ospiti)': 'departures_guests',
}

def load_config(path: str) -> dict:
    cfg = {'rooms_default': 5, 'currency_symbol': '€', 'locale_date_format': '%d/%m/%Y'}
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg.update(user_cfg)
    return cfg

def _normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = {}
    for c in df.columns:
        low = re.sub(r"\s+", " ", str(c)).strip().lower()
        new_cols[c] = HEADER_MAP.get(low, low)
    df = df.rename(columns=new_cols)
    return df

def _drop_totali_mese(df: pd.DataFrame) -> pd.DataFrame:
    if 'date' in df.columns:
        mask_ok = ~df['date'].astype(str).str.lower().str.contains('totale')
        df = df.loc[mask_ok].copy()
    df = df.dropna(how='all')
    return df


def _parse_dates(df: pd.DataFrame, date_format: str) -> pd.DataFrame:
    if 'date' not in df.columns:
        raise ValueError("Colonna 'Data' (date) mancante dopo normalizzazione.")
    # 1) tentativo con formato esplicito
    s1 = pd.to_datetime(df['date'], format=date_format, errors='coerce')
    # 2) se il 50%+ è NaT, prova parsing libero (ISO/varie)
    if s1.isna().mean() > 0.5:
        s2 = pd.to_datetime(df['date'], errors='coerce')
        # 3) se ancora alto, prova con dayfirst=True
        if s2.isna().mean() > 0.5:
            s3 = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            best = s3 if s3.isna().mean() < s2.isna().mean() else s2
        else:
            best = s2
    else:
        best = s1
    df['date'] = best
    df = df.dropna(subset=['date']).copy()
    return df

def normalize_wide_excel(xls_bytes, config: dict, property_name: str) -> pd.DataFrame:
    """
    Legge un Excel KrossBooking (bytes o BytesIO) e restituisce DataFrame normalizzato giornaliero
    con colonna 'property' impostata a property_name.
    """
    xls = pd.ExcelFile(xls_bytes)
    frames = []
    for sheet in xls.sheet_names:
        df = xls.parse(sheet_name=sheet)
        if df.empty:
            continue
        df = _normalize_headers(df)
        df = _drop_totali_mese(df)
        df = _parse_dates(df, config.get('locale_date_format', '%d/%m/%Y'))
        frames.append(df)
    if not frames:
        raise ValueError("Excel senza dati utilizzabili.")
    df = pd.concat(frames, ignore_index=True)

    # Normalizza tipi numerici
    for col in ['rooms_total', 'rooms_blocked', 'rooms_sold']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    for col in ['rooms_blocked_pct', 'occ_pct', 'adr', 'revpar', 'revenue']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    if 'rooms_total' not in df.columns or df['rooms_total'].isna().all():
        df['rooms_total'] = config.get('rooms_default', 5)

    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['month_name'] = df['date'].dt.strftime('%B')
    df['property'] = property_name
    return df

def month_bounds(dt: datetime) -> tuple[datetime, datetime]:
    start = dt.replace(day=1)
    end = (start + relativedelta(months=1)) - relativedelta(days=1)
    return start, end
