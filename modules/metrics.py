# -*- coding: utf-8 -*-
from __future__ import annotations

import calendar
import pandas as pd

def _rooms_nominali(df_month: pd.DataFrame, rooms_default: int) -> int:
    if 'rooms_total' in df_month.columns and df_month['rooms_total'].notna().any():
        return int(df_month['rooms_total'].mode(dropna=True).iloc[0])
    return int(rooms_default)

def kpis_month(df: pd.DataFrame, year: int, month: int, rooms_default: int) -> dict:
    dfm = df[(df['year'] == year) & (df['month'] == month)].copy()
    if dfm.empty:
        return {'revenue': 0.0, 'occ_pct': 0.0, 'adr': 0.0, 'revpar': 0.0, 'notti': 0, 'rooms_nominali': rooms_default, 'giorni': calendar.monthrange(year, month)[1]}

    giorni = calendar.monthrange(year, month)[1]
    rooms_nom = _rooms_nominali(dfm, rooms_default)
    disponibili = rooms_nom * giorni

    revenue = float(dfm['revenue'].sum(skipna=True)) if 'revenue' in dfm else 0.0
    notti = int(dfm['rooms_sold'].sum(skipna=True)) if 'rooms_sold' in dfm else 0
    adr = float(dfm['adr'].mean(skipna=True)) if 'adr' in dfm else 0.0
    revpar = float(dfm['revpar'].mean(skipna=True)) if 'revpar' in dfm else 0.0
    occ_pct = (notti / disponibili * 100.0) if disponibili > 0 else 0.0

    return {'revenue': revenue, 'occ_pct': occ_pct, 'adr': adr, 'revpar': revpar, 'notti': notti, 'rooms_nominali': rooms_nom, 'giorni': giorni}

def yoy_vs(prev: dict, curr: dict) -> dict:
    return {
        'Δ_revenue': curr['revenue'] - prev['revenue'],
        'Δ_occ_pp': curr['occ_pct'] - prev['occ_pct'],
        'Δ_adr': curr['adr'] - prev['adr'],
        'Δ_revpar': curr['revpar'] - prev['revpar'],
        'Δ_notti': curr['notti'] - prev['notti'],
    }

def month_overview(df: pd.DataFrame, year: int, month: int, rooms_default: int) -> dict:
    curr = kpis_month(df, year, month, rooms_default)
    prev = kpis_month(df, year - 1, month, rooms_default)
    delta = yoy_vs(prev, curr)
    return {'curr': curr, 'prev': prev, 'delta': delta}

def filter_by_properties(df: pd.DataFrame, properties: list[str]) -> pd.DataFrame:
    if not properties:
        return df.iloc[0:0].copy()
    return df[df['property'].isin(properties)].copy()

def next_6_months(df: pd.DataFrame, start_year: int, start_month: int, rooms_default: int) -> pd.DataFrame:
    rows = []
    y, m = start_year, start_month
    for _ in range(6):
        k = kpis_month(df, y, m, rooms_default)
        rows.append({'anno': y, 'mese': m, 'revenue': k['revenue'], 'occ_pct': k['occ_pct'], 'adr': k['adr'], 'revpar': k['revpar'], 'notti': k['notti']})
        m += 1
        if m == 13:
            m = 1
            y += 1
    return pd.DataFrame(rows)
