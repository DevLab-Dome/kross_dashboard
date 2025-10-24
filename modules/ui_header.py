
"""
ui_header.py — Header bar component for Kross Dashboard
DevLab – Hospitality Software

Scopo: componente riutilizzabile per la parte alta della dashboard (mese corrente, nav ◀ ▶, KPI sintetici).
NOTE:
  - Questo file NON modifica lo stato dell'app. Fornisce solo il rendering UI del blocco header.
  - Le funzioni espongono parametri semplici da collegare ai tuoi dati reali nel passo successivo.

Dipendenze: streamlit
"""

from __future__ import annotations
from typing import Dict, Optional
import streamlit as st

# --- STYLE HELPERS ---------------------------------------------------------------------------
def _delta_badge(value: float, suffix: str = "", positive_is_good: bool = True) -> str:
    """Ritorna HTML per badge delta (verde=positivo, rosso=negativo).
    Esempi:
      _delta_badge(+3.87, "%")  -> verde  +3.87%
      _delta_badge(-785.58, "€") -> rosso  -785.58€
    """
    color_pos = "#138000"  # verde
    color_neg = "#C00000"  # rosso
    sign = "+" if value > 0 else ""  # mostra + davanti ai positivi
    # Nota: se positive_is_good=False (es. costi), inverti la logica del colore
    good = (value >= 0 and positive_is_good) or (value < 0 and not positive_is_good)
    color = color_pos if good else color_neg
    return f'<span style="font-weight:600;color:{color}">{sign}{value:,.2f}{suffix}</span>'

def _kpi_block(title: str, value: str, delta_html: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """Stampa un blocco KPI compatto con titolo, valore e (opzionale) delta colorato."""
    st.markdown(f"**{title}**")
    st.markdown(f"<div style='font-size:1.6rem;line-height:1.2'>{value}</div>", unsafe_allow_html=True)
    if delta_html:
        st.markdown(delta_html, unsafe_allow_html=True)
    if help_text:
        st.caption(help_text)

# --- PUBLIC RENDERER -------------------------------------------------------------------------
def render_header_bar(
    month_label: str,
    prev_month_label: str,
    next_month_label: str,
    kpi: Dict[str, str],
    deltas: Optional[Dict[str, float]] = None,
    key_prefix: str = "hdr",
) -> Dict[str, bool]:
    """Render della barra superiore della dashboard.

    Parametri
    ---------
    month_label        : etichetta del mese corrente (es. "Ottobre 2025").
    prev_month_label   : etichetta per il mese precedente (es. "Settembre").
    next_month_label   : etichetta per il mese successivo (es. "Novembre").
    kpi                : dizionario string->string con i valori già formattati, chiavi consigliate:
                         {
                           "Revenue": "€ 18.705,84",
                           "Occupazione": "99,35%",
                           "Notti vendute": "154",
                           "ADR": "€ 121,54",
                           "RevPAR": "€ 120,68"
                         }
    deltas             : opzionale, dizionario string->float con delta YoY o MoM in valore assoluto
                         (non in % salvo tu voglia passare già la %), chiavi: "Revenue", "Occupazione", ...
    key_prefix         : prefisso per le chiavi Streamlit (utile quando si inserisce più volte il componente).

    Ritorno
    -------
    dict con flag dei pulsanti: {"prev_clicked": bool, "next_clicked": bool}
    """
    deltas = deltas or {}
    st.markdown("---")
    container = st.container()
    with container:
        # Riga 1: Navigazione mese
        nav_left, nav_center, nav_right = st.columns([1, 3, 1])
        with nav_left:
            prev_clicked = st.button(f"◀ {prev_month_label}", key=f"{key_prefix}_prev")
        with nav_center:
            st.markdown(
                f"<div style='text-align:center;font-size:1.25rem;font-weight:700'>{month_label}</div>",
                unsafe_allow_html=True,
            )
        with nav_right:
            next_clicked = st.button(f"{next_month_label} ▶", key=f"{key_prefix}_next")

        st.markdown("")

        # Riga 2: KPI compatti (5 colonne)
        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            d = deltas.get("Revenue")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("Revenue (mese)", kpi.get("Revenue", "-"), badge)

        with c2:
            d = deltas.get("Occupazione")
            # Per Occupazione, delta espresso in punti percentuali (es. +3,87 pp) se passi float (0-100)
            badge = _delta_badge(d, "%", positive_is_good=True) if d is not None else None
            _kpi_block("Occupazione", kpi.get("Occupazione", "-"), badge, help_text="Camere vendute / (Camere * giorni)")

        with c3:
            d = deltas.get("Notti vendute")
            badge = _delta_badge(d, "", positive_is_good=True) if d is not None else None
            _kpi_block("Notti vendute", kpi.get("Notti vendute", "-"), badge)

        with c4:
            d = deltas.get("ADR")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("ADR", kpi.get("ADR", "-"), badge, help_text="Media giornaliera ADR")

        with c5:
            d = deltas.get("RevPAR")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("RevPAR", kpi.get("RevPAR", "-"), badge, help_text="Media giornaliera RevPAR")

    st.markdown("---")
    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

