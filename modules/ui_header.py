# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Optional
import streamlit as st

# -----------------------------------------------------------------------------
# Helpers grafici (badge Δ e blocchi KPI)
# -----------------------------------------------------------------------------
def _delta_badge(delta: Optional[float], suffix: str = "", positive_is_good: bool = True) -> str:
    if delta is None:
        return ""
    good = delta >= 0 if positive_is_good else delta <= 0
    color = "#1a7f37" if good else "#b60205"
    sign = "+" if delta > 0 else ""
    val = f"{sign}{delta:.2f}{suffix}".replace(".", ",")
    return f"<span style='margin-left:6px;color:{color};font-weight:700'>{val}</span>"

def _kpi_block(title: str, value_fmt: str, badge_html: Optional[str] = None, help_text: Optional[str] = None) -> None:
    if help_text:
        st.caption(help_text)
    st.markdown(f"<div style='font-size:0.95rem;font-weight:600'>{title}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-size:1.2rem;font-weight:800'>{value_fmt}{badge_html or ''}</div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# NAV 5 colonne (prev su col 1, centro su col 3, next su col 5) – base per ANNO/MESE
# -----------------------------------------------------------------------------
def _render_nav_5cols(prev_text: str, center_html: str, next_text: str, key_prefix: str) -> Dict[str, bool]:
    g1, g2, g3, g4, g5 = st.columns(5)

    with g1:
        _l, _c, _r = st.columns([1, 1, 1])    # bottone centrato
        with _c:
            prev_clicked = st.button(prev_text, key=f"{key_prefix}_prev")

    with g3:
        st.markdown(
            f"<div style='text-align:center; font-size:1.1rem; font-weight:700;'>{center_html}</div>",
            unsafe_allow_html=True,
        )

    with g5:
        _l2, _c2, _r2 = st.columns([1, 1, 1])  # bottone centrato
        with _c2:
            next_clicked = st.button(next_text, key=f"{key_prefix}_next")

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# -----------------------------------------------------------------------------
# Header (MESE): nav + (opzionali) KPI mese
# -----------------------------------------------------------------------------
def render_header_bar(
    month_label: str,
    prev_month_label: str,
    next_month_label: str,
    kpi: Dict[str, str],
    deltas: Optional[Dict[str, float]] = None,
    key_prefix: str = "hdr",
    show_kpis: bool = True,
) -> Dict[str, bool]:
    """Barra superiore della dashboard (mese corrente)."""
    deltas = deltas or {}
    st.markdown("")  # separatore superiore

    with st.container():
        clicks = _render_nav_5cols(
            prev_text=prev_month_label,
            center_html=month_label,
            next_text=next_month_label,
            key_prefix=key_prefix,
        )

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        if show_kpis:
            c1, c2, c3, c4, c5 = st.columns(5)

            with c1:
                d = deltas.get("Revenue")
                _kpi_block("Revenue (mese)", kpi.get("Revenue", "-"),
                           _delta_badge(d, "€", True) if d is not None else None,
                           "Somma Totale revenue del mese")
            with c2:
                d = deltas.get("Occupazione")
                _kpi_block("Occupazione", kpi.get("Occupazione", "-"),
                           _delta_badge(d, " pp", True) if d is not None else None,
                           "Camere vendute / (Camere * giorni)")
            with c3:
                d = deltas.get("Notti vendute")
                _kpi_block("Notti vendute", kpi.get("Notti vendute", "-"),
                           _delta_badge(d, "", True) if d is not None else None,
                           "Somma notti vendute nel mese")
            with c4:
                d = deltas.get("ADR")
                _kpi_block("ADR", kpi.get("ADR", "-"),
                           _delta_badge(d, "€", True) if d is not None else None,
                           "Media giornaliera ADR")
            with c5:
                d = deltas.get("RevPAR")
                _kpi_block("RevPAR", kpi.get("RevPAR", "-"),
                           _delta_badge(d, "€", True) if d is not None else None,
                           "Media giornaliera RevPAR")

        st.markdown("---")

    return clicks

# -----------------------------------------------------------------------------
# Year NAV (solo bottoni/label – identica struttura/sizing della nav mese)
# -----------------------------------------------------------------------------
def render_year_nav(current_year: int, key_prefix: str = "ynav") -> Dict[str, bool]:
    prev_text = str(current_year - 1)
    next_text = str(current_year + 1)
    center_html = f"Anno {current_year}"
    return _render_nav_5cols(prev_text, center_html, next_text, key_prefix)

# -----------------------------------------------------------------------------
# Barra KPI per l'ANNO (5 KPI, senza bottoni)
# -----------------------------------------------------------------------------
def render_year_bar(
    title_html: str,   # mantenuto per compatibilità
    kpi: Dict[str, str],
    deltas: Optional[Dict[str, float]] = None,
    key_prefix: str = "ybar",
) -> None:
    deltas = deltas or {}
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        d = deltas.get("Revenue")
        _kpi_block("Revenue (anno)", kpi.get("Revenue", "-"),
                   _delta_badge(d, "€", True) if d is not None else None,
                   "Somma Totale revenue dell'anno")
    with c2:
        d = deltas.get("Occupazione")
        _kpi_block("Occupazione", kpi.get("Occupazione", "-"),
                   _delta_badge(d, " pp", True) if d is not None else None,
                   "Notti / Camere disponibili * 100")
    with c3:
        d = deltas.get("Notti vendute")
        _kpi_block("Notti vendute", kpi.get("Notti vendute", "-"),
                   _delta_badge(d, "", True) if d is not None else None,
                   "Somma notti vendute nell'anno")
    with c4:
        d = deltas.get("ADR")
        _kpi_block("ADR medio", kpi.get("ADR", "-"),
                   _delta_badge(d, "€", True) if d is not None else None,
                   "Media giornaliera ADR (anno)")
    with c5:
        d = deltas.get("RevPAR")
        _kpi_block("RevPAR medio", kpi.get("RevPAR", "-"),
                   _delta_badge(d, "€", True) if d is not None else None,
                   "Media giornaliera RevPAR (anno)")

    st.markdown("---")
