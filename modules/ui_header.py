"""
ui_header.py — Header & Year bars for Kross Dashboard
DevLab – Hospitality Software

Componenti riutilizzabili per:
- barra mese con navigazione ◀ ▶ (opzionale: mostrare i 5 KPI del mese)
- barra anno (5 KPI annuali)

Convenzioni:
- Occupazione: badge Δ in punti percentuali (pp)
- Revenue/Notti: Δ in valore assoluto
- ADR/RevPAR: Δ in valore assoluto
"""

from __future__ import annotations
from typing import Dict, Optional
import streamlit as st
def inject_base_styles():
    import streamlit as st
    st.markdown(
        """
        <style>
        :root{
            --dl-font: ui-sans-serif, -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
            --dl-muted:#6b7280;
            --dl-fg:#0f172a;
            --dl-accent:#1f6feb;
            --dl-bg:#ffffff;
            --dl-ring:rgba(31,111,235,.25);
            --dl-radius:10px;
            --dl-pad:10px 12px;
            --dl-gap:8px;
            --dl-chip-bg:#f8fafc;
            --dl-chip-fg:#0f172a;
        }
        .dl-root, .dl-root *{ font-family: var(--dl-font); letter-spacing: .2px; }
        .dl-strip{ display:flex; align-items:center; gap: var(--dl-gap); background: var(--dl-bg); border:1px solid #e5e7eb; border-radius: var(--dl-radius); padding: 8px 10px; margin: 6px 0; }
        .dl-title{ font-weight:600; color:var(--dl-fg); white-space:nowrap; padding-right:8px; border-right:1px solid #e5e7eb; }
        .dl-actions{ display:flex; gap:6px; flex-wrap:wrap; }
        div.stButton>button{ padding: var(--dl-pad); border-radius: 8px; border:1px solid #d1d5db; background:#fff; }
        div.stButton>button:hover{ border-color: var(--dl-accent); box-shadow:0 0 0 3px var(--dl-ring); }
        div.stButton>button:focus{ outline:none; box-shadow:0 0 0 3px var(--dl-ring); }
        .dl-chip{ background: var(--dl-chip-bg); color: var(--dl-chip-fg); border-radius:999px; padding:4px 10px; font-size:0.9rem; font-weight:600; }
        .dl-hint{ color:var(--dl-muted); font-size:0.85rem; }
        </style>
        """,
        unsafe_allow_html=True
    )

# --- STYLE HELPERS ---------------------------------------------------------------------------

def _delta_badge(value: float, suffix: str = "", positive_is_good: bool = True) -> str:
    """Ritorna HTML per badge delta (verde=positivo, rosso=negativo)."""
    color_pos = "#138000"  # verde
    color_neg = "#C00000"  # rosso
    sign = "+" if value > 0 else ""
    good = (value >= 0 and positive_is_good) or (value < 0 and not positive_is_good)
    color = color_pos if good else color_neg
    return f'<span style="font-weight:600;color:{color}">{sign}{value:,.2f}{suffix}</span>'

def _kpi_block(title: str, value: str, delta_html: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """Blocco KPI compatto con titolo, valore e (opzionale) delta colorato."""
    st.markdown(f"<div style='font-size:0.95rem;font-weight:600'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:2.0rem;line-height:1.2;font-weight:400'>{value}</div>", unsafe_allow_html=True)
    if delta_html:
        st.markdown(delta_html, unsafe_allow_html=True)
    if help_text:
        st.caption(help_text)
        
# --- NAVIGAZIONE ANNO ------------------------------------------------------------------------
def render_year_nav(
    current_year: int,
    key_prefix: str = "yhdr",
    prev_label: str | None = None,
    next_label: str | None = None,
) -> dict:
    """
    Due bottoni PREV/NEXT con il titolo 'Anno {current_year}' centrato tra i due.
    Ritorna: {"prev_clicked": bool, "next_clicked": bool}
    """
    import streamlit as st  # ok anche se già importato in alto

    prev_text = prev_label if prev_label is not None else str(current_year - 1)
    next_text = next_label if next_label is not None else str(current_year + 1)

    cols = st.columns([1, 3, 1])
    with cols[0]:
        prev_clicked = st.button(prev_text, key=f"{key_prefix}_prev")
    with cols[1]:
        st.markdown(
            f"<div style='text-align:center; font-size:1.1rem; font-weight:700;'>Anno {current_year}</div>",
            unsafe_allow_html=True,
        )
    with cols[2]:
        next_clicked = st.button(next_text, key=f"{key_prefix}_next")

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# --- HEADER (MESE) ---------------------------------------------------------------------------

def render_header_bar(
    month_label: str,
    prev_month_label: str,
    next_month_label: str,
    kpi: Dict[str, str],
    deltas: Optional[Dict[str, float]] = None,
    key_prefix: str = "hdr",
    show_kpis: bool = True,
) -> Dict[str, bool]:
    """
    Barra superiore della dashboard (mese corrente).
    Ritorna: {"prev_clicked": bool, "next_clicked": bool}
    """
    deltas = deltas or {}

    # Separatore superiore (vuoto, niente riga)
    st.markdown("")

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

        # Spacer sottile
        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        # Riga 2: KPI compatti (opzionale)
        if show_kpis:
            c1, c2, c3, c4, c5 = st.columns(5)

            with c1:
                d = deltas.get("Revenue")
                badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
                _kpi_block("Revenue (mese)", kpi.get("Revenue", "-"), badge, help_text="Somma Totale revenue del mese")

            with c2:
                d = deltas.get("Occupazione")
                badge = _delta_badge(d, " pp", positive_is_good=True) if d is not None else None
                _kpi_block("Occupazione", kpi.get("Occupazione", "-"), badge, help_text="Camere vendute / (Camere * giorni)")

            with c3:
                d = deltas.get("Notti vendute")
                badge = _delta_badge(d, "", positive_is_good=True) if d is not None else None
                _kpi_block("Notti vendute", kpi.get("Notti vendute", "-"), badge, help_text="Somma notti vendute nel mese")

            with c4:
                d = deltas.get("ADR")
                badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
                _kpi_block("ADR", kpi.get("ADR", "-"), badge, help_text="Media giornaliera ADR")

            with c5:
                d = deltas.get("RevPAR")
                badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
                _kpi_block("RevPAR", kpi.get("RevPAR", "-"), badge, help_text="Media giornaliera RevPAR")

    # Separatore inferiore
    st.markdown("---")
    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# --- YEAR BAR (ANNO) -------------------------------------------------------------------------

def render_year_bar(
    title_html: str,
    kpi: Dict[str, str],
    deltas: Optional[Dict[str, float]] = None,
    key_prefix: str = "ybar",
) -> None:
    """
    Barra KPI per l'ANNO (5 KPI, senza bottoni).
    - title_html: es. "Anno corrente<br><span style='font-size:0.9rem;font-weight:400'>(vs 2024)</span>"
    - kpi: {"Revenue": "...", "Occupazione": "...", "Notti vendute": "...", "ADR": "...", "RevPAR": "..."}
    - deltas: differenze YoY (Occupazione in pp)
    """
    deltas = deltas or {}
    box = st.container()
    with box:

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            d = deltas.get("Revenue")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("Revenue (anno)", kpi.get("Revenue", "-"), badge, help_text="Somma Totale revenue dell'anno")

        with c2:
            d = deltas.get("Occupazione")
            badge = _delta_badge(d, " pp", positive_is_good=True) if d is not None else None
            _kpi_block("Occupazione", kpi.get("Occupazione", "-"), badge, help_text="Notti / Camere disponibili * 100")

        with c3:
            d = deltas.get("Notti vendute")
            badge = _delta_badge(d, "", positive_is_good=True) if d is not None else None
            _kpi_block("Notti vendute", kpi.get("Notti vendute", "-"), badge, help_text="Somma notti vendute nell'anno")

        with c4:
            d = deltas.get("ADR")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("ADR medio", kpi.get("ADR", "-"), badge, help_text="Media giornaliera ADR (anno)")

        with c5:
            d = deltas.get("RevPAR")
            badge = _delta_badge(d, "€", positive_is_good=True) if d is not None else None
            _kpi_block("RevPAR medio", kpi.get("RevPAR", "-"), badge, help_text="Media giornaliera RevPAR (anno)")
    st.markdown("---")
