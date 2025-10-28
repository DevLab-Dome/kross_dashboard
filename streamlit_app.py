# -*- coding: utf-8 -*-
from __future__ import annotations

import io, os
from datetime import datetime

import pandas as pd
import streamlit as st

from modules.data_loader import load_config, normalize_wide_excel
from modules.metrics import month_overview, next_6_months, filter_by_properties

# -----------------------------------------------------------------------------
# STILI BASE (unica definizione)
# -----------------------------------------------------------------------------
def inject_base_styles():
    st.markdown("""
<style>
:root{
    --dl-font: ui-sans-serif, -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
    --dl-muted:#6b7280; --dl-fg:#0f172a; --dl-accent:#1f6feb; --dl-bg:#ffffff;
    --dl-ring:rgba(31,111,235,.25); --dl-radius:10px; --dl-pad:10px 12px; --dl-gap:8px;
    --dl-chip-bg:#f8fafc; --dl-chip-fg:#0f172a;
}
.dl-root, .dl-root *{ font-family: var(--dl-font); letter-spacing: .2px; }

div.stButton>button{
    padding: var(--dl-pad);
    border-radius: 8px; border:1px solid #cbd5e1;
    background:#fff !important; color: var(--dl-fg) !important; font-weight: 600;
    transition: border-color .12s ease, box-shadow .12s ease;
    white-space: nowrap; min-width: 96px;
}
div.stButton>button:hover{ border-color: var(--dl-accent); box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:focus{ outline:none; box-shadow:0 0 0 3px var(--dl-ring); }
div.stButton>button:disabled{
    background: var(--dl-chip-bg) !important; color: var(--dl-chip-fg) !important;
    border-color: #cbd5e1 !important; font-weight: 700 !important;
    cursor: default !important; opacity: 1 !important; box-shadow: none !important;
}

/* Header mese */
.mh-under{color:#0f172a;opacity:.6;font-size:15px;text-align:center;margin-top:2px;}
.mh-center{text-align:center;margin-top:2px;}
.mh-month{font-weight:700;font-size:28px;line-height:1.1;margin:0;}
.mh-sub{color:#6b7280;font-size:13px;margin-top:2px;}
div.mh-btn{ margin-bottom:2px; }
div.mh-btn > button{
  border:1px solid #e5e7eb !important; border-radius:10px !important;
  background:#ffffff !important; font-weight:700 !important; font-size:18px !important;
  min-height:44px; min-width:120px; margin-bottom:0 !important;
}
div.mh-btn > button:hover{
  border-color:#1f6feb !important; box-shadow:0 0 0 3px rgba(31,111,235,.25) !important;
}

/* KPI mese */
.kpi-col{ width:100%; display:flex; flex-direction:column; align-items:center; }
.kpi-label{ font-size:14px; color:#6b7280; margin-bottom:6px; white-space:nowrap; }
.kpi-value{ font-size:36px; font-weight:700; color:#111827; line-height:1.15; white-space:nowrap; }
.kpi-pill{ display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px;
           font-size:13px; font-weight:600; margin-top:8px; }
.kpi-pill.up{ background:#ecfdf5; color:#16a34a; }
.kpi-pill.down{ background:#fef2f2; color:#dc2626; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE CONFIG + TITLE
# -----------------------------------------------------------------------------
st.set_page_config(page_title="DevLab – Kross Dashboard", layout="wide", initial_sidebar_state="collapsed")
inject_base_styles()
st.markdown('<div class="dl-root"></div>', unsafe_allow_html=True)
# ─────────────────────────────────────────────────────────────────────────────
# RENDERER NUOVE STRISCE PICK-UP (MESE/ANNO) — solo UI, zero side-effect
# Classi CSS namespaced: .pu-… per non toccare le strisce attuali
# ─────────────────────────────────────────────────────────────────────────────
from typing import Dict, Literal

def _pu_grid():
    """Griglia identica alle strisce correnti: [2,1,3,1,2]."""
    return st.columns([2, 1, 3, 1, 2], gap="large")

def _pu_styles():
    st.markdown("""
<style>
.pu-col{ width:100%; display:flex; flex-direction:column; align-items:center; }
.pu-label{ font-size:14px; color:#6b7280; margin-bottom:6px; white-space:nowrap; }
.pu-value{ font-size:36px; font-weight:400; color:#111827; line-height:1.15; white-space:nowrap; }
.pu-pill{ display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px;
          font-size:13px; font-weight:600; margin-top:8px; }
.pu-pill.up{ background:#ecfdf5; color:#16a34a; }
.pu-pill.down{ background:#fef2f2; color:#dc2626; }
</style>
""", unsafe_allow_html=True)

def _pu_pill(delta: float) -> str:
    """Pillola Δ (verde/rosso) con formattazione italiana."""
    if delta is None:
        return ""
    cls  = "up" if delta >= 0 else "down"
    icon = "↑" if delta >= 0 else "↓"
    val  = f"{delta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f'<span class="pu-pill {cls}">{icon} {val}</span>'

def _pu_format(cur: float, kind: Literal["eur","pct","int"]="eur") -> str:
    """
    Usa i formatter GIÀ esistenti (_fmt_eur/_fmt_pct/_fmt_th) senza modificarli.
    """
    if kind == "pct":
        return _fmt_pct(cur or 0.0)
    if kind == "int":
        return _fmt_th(int(cur or 0))
    return _fmt_eur(cur or 0.0)

def render_pickup_strip(kpi_cur: Dict[str, float], kpi_delta: Dict[str, float], titolo: str):
    """
    Renderer per nuove strisce Pick-up (possono convivere nelle sezioni esistenti).
    Nessun accesso ai dati qui: solo presentazione.
    Attesi:
      kpi_cur   = {"Revenue":f, "Occupazione":f, "Notti vendute":f, "ADR":f, "RevPAR":f}
      kpi_delta = stessi key, Δ (oggi - ieri)
    """
    _pu_styles()
    st.subheader(titolo, divider=False)

    col_rev, col_occ, col_notti, col_adr, col_rpar = _pu_grid()

    with col_rev:
        st.markdown('<div class="pu-col">', unsafe_allow_html=True)
        st.markdown('<div class="pu-label">Revenue</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pu-value">{_pu_format(kpi_cur.get("Revenue",0.0),"eur")}</div>{_pu_pill(kpi_delta.get("Revenue",0.0))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_occ:
        st.markdown('<div class="pu-col">', unsafe_allow_html=True)
        st.markdown('<div class="pu-label">Occupazione</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pu-value">{_pu_format(kpi_cur.get("Occupazione",0.0),"pct")}</div>{_pu_pill(kpi_delta.get("Occupazione",0.0))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_notti:
        st.markdown('<div class="pu-col">', unsafe_allow_html=True)
        st.markdown('<div class="pu-label">Notti vendute</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pu-value">{_pu_format(kpi_cur.get("Notti vendute",0.0),"int")}</div>{_pu_pill(kpi_delta.get("Notti vendute",0.0))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_adr:
        st.markdown('<div class="pu-col">', unsafe_allow_html=True)
        st.markdown('<div class="pu-label">ADR</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pu-value">{_pu_format(kpi_cur.get("ADR",0.0),"eur")}</div>{_pu_pill(kpi_delta.get("ADR",0.0))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_rpar:
        st.markdown('<div class="pu-col">', unsafe_allow_html=True)
        st.markdown('<div class="pu-label">RevPAR</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="pu-value">{_pu_format(kpi_cur.get("RevPAR",0.0),"eur")}</div>{_pu_pill(kpi_delta.get("RevPAR",0.0))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# PICK-UP DATA WIRE-UP (MESE) — usa gli snapshot salvati + renderer .pu-*
# Non modifica nulla di esistente: aggiunge una striscia opzionale in coda
# ─────────────────────────────────────────────────────────────────────────────
from datetime import date
import pandas as pd

try:
    from modules.pickup_engine import pickup_between
except Exception as _e:
    st.warning("Pick-up Engine non disponibile. Aggiungi modules/pickup_engine.py al repo.")
    pickup_between = None

DB_PATH = ".devlab/data/snapshots.db"

with st.container(border=True):
    st.caption("Nuova striscia • Pick-up Giornaliero — MESE (sperimentale)")
    colL, colR = st.columns([3, 2], gap="large")
    with colL:
        as_of = st.date_input("As-of (fotografia odierna)", value=date.today())
        prev_auto = st.checkbox("Confronta con ultimo snapshot precedente (auto)", value=True)
        prev_date = None if prev_auto else st.date_input("Confronta con (data precedente)", value=date.today())
    with colR:
        property_filter = st.text_input("Property (lascia vuoto per tutte)", value="")

    if pickup_between is not None:
        df_pick = pickup_between(
            DB_PATH,
            as_of_current=as_of,
            as_of_prev=prev_date,
            property_name=(property_filter or None)
        )

        if df_pick.empty:
            st.info("Nessuno snapshot trovato per la data selezionata. Importa prima i forecast con otb_snapshots.py.")
        else:
            # Selezione mese/anno di soggiorno da visualizzare
            df_pick["mese_label"] = pd.to_datetime(
                df_pick["stay_year"].astype(str) + "-" + df_pick["stay_month"].astype(str) + "-01"
            ).dt.strftime("%B %Y").str.capitalize()

            mcol1, mcol2 = st.columns([2, 3])
            with mcol1:
                # Ordina discendente per anno/mese
                options = df_pick.sort_values(["stay_year","stay_month"], ascending=[False, False])["mese_label"].unique().tolist()
                mese_sel = st.selectbox("Mese di soggiorno", options=options, index=0 if options else None)
            with mcol2:
                st.write("")

            # Estrae la riga aggregata del mese scelto (se property vuota, somma su tutte)
            view = df_pick[df_pick["mese_label"] == mese_sel].copy()
            if property_filter == "":
                # Somma su tutte le property (mese selezionato)
                keys = ["revenue","nights_sold","rooms_available","occupancy_pct","adr","revpar"]
                sums = {k+"_cur": view[k+"_cur"].sum() for k in keys}
                sums.update({k+"_prev": view[k+"_prev"].sum() for k in keys})
                sums.update({k+"_delta": view[k+"_delta"].sum() for k in keys})
                # Delta % come media semplice (proxy)
                sums.update({k+"_delta_pct": view[k+"_delta_pct"].mean() for k in keys})
                row = pd.Series(sums)
            else:
                # Una sola property → ci aspettiamo 1 riga; se più righe, somma come sopra
                if len(view) > 1:
                    keys = ["revenue","nights_sold","rooms_available","occupancy_pct","adr","revpar"]
                    sums = {k+"_cur": view[k+"_cur"].sum() for k in keys}
                    sums.update({k+"_prev": view[k+"_prev"].sum() for k in keys})
                    sums.update({k+"_delta": view[k+"_delta"].sum() for k in keys})
                    sums.update({k+"_delta_pct": view[k+"_delta_pct"].mean() for k in keys})
                    row = pd.Series(sums)
                else:
                    row = view.squeeze()

            # Mappa verso il renderer UI (valori correnti + Δ assolute)
            kpi_cur = {
                "Revenue":       float(row.get("revenue_cur", 0.0)),
                "Occupazione":   float(row.get("occupancy_pct_cur", 0.0)),
                "Notti vendute": float(row.get("nights_sold_cur", 0.0)),
                "ADR":           float(row.get("adr_cur", 0.0)),
                "RevPAR":        float(row.get("revpar_cur", 0.0)),
            }
            kpi_delta = {
                "Revenue":       float(row.get("revenue_delta", 0.0)),
                "Occupazione":   float(row.get("occupancy_pct_delta", 0.0)),
                "Notti vendute": float(row.get("nights_sold_delta", 0.0)),
                "ADR":           float(row.get("adr_delta", 0.0)),
                "RevPAR":        float(row.get("revpar_delta", 0.0)),
            }

            render_pickup_strip(kpi_cur, kpi_delta, titolo=f"Pick-up Giornaliero — {mese_sel}")
# ─────────────────────────────────────────────────────────────────────────────
# PICK-UP DATA WIRE-UP (ANNO) — nuova striscia appended in coda, no changes al resto
# Aggregazione annuale:
#  - Revenue/Notti/Rooms: somma
#  - Occupazione %: (somma notti / somma rooms) * 100
#  - ADR/RevPAR: media semplice dei mesi disponibili (proxy)
# ─────────────────────────────────────────────────────────────────────────────
from datetime import date
import numpy as np
import pandas as pd

try:
    from modules.pickup_engine import pickup_between
except Exception as _e:
    st.warning("Pick-up Engine non disponibile. Aggiungi modules/pickup_engine.py al repo.")
    pickup_between = None

DB_PATH = "…/…/.devlab/data/snapshots.db" if "DB_PATH" not in globals() else DB_PATH  # riusa se già definito

with st.container(border=True):
    st.caption("Nuova striscia • Pick-up Giornaliero — ANNO (sperimentale)")

    colL, colR = st.columns([3, 2], gap="large")
    with colL:
        as_of_y = st.date_input("As-of (fotografia odierna)", value=date.today(), key="asof_year")
        prev_auto_y = st.checkbox("Confronta con ultimo snapshot precedente (auto)", value=True, key="auto_prev_year")
        prev_date_y = None if prev_auto_y else st.date_input("Confronta con (data precedente)", value=date.today(), key="prev_year")
    with colR:
        property_filter_y = st.text_input("Property (lascia vuoto per tutte)", value="", key="prop_year")

    if pickup_between is not None:
        df_pick_y = pickup_between(
            DB_PATH,
            as_of_current=as_of_y,
            as_of_prev=prev_date_y,
            property_name=(property_filter_y or None)
        )

        if df_pick_y.empty:
            st.info("Nessuno snapshot trovato per la data selezionata. Importa prima i forecast con otb_snapshots.py.")
        else:
            # Selettore anno (dati presenti)
            anni = sorted(df_pick_y["stay_year"].dropna().astype(int).unique().tolist(), reverse=True)
            year_sel = st.selectbox("Anno di soggiorno", options=anni, index=0 if anni else None)

            # Filtra anno
            ydf = df_pick_y[df_pick_y["stay_year"] == year_sel].copy()

            # Se property vuota: somma cross-property; se piena: già filtrato a monte
            # Somme "strutturali"
            def _sum(k): return float(pd.to_numeric(ydf[k], errors="coerce").fillna(0.0).sum())
            nights_cur  = _sum("nights_sold_cur")
            nights_prev = _sum("nights_sold_prev")
            rooms_cur   = _sum("rooms_available_cur")
            rooms_prev  = _sum("rooms_available_prev")

            revenue_cur  = _sum("revenue_cur")
            revenue_prev = _sum("revenue_prev")
            revenue_delta = revenue_cur - revenue_prev

            # Occupazione come rapporto (non somma di %)
            occ_cur  = (nights_cur / rooms_cur * 100.0) if rooms_cur > 0 else 0.0
            occ_prev = (nights_prev / rooms_prev * 100.0) if rooms_prev > 0 else 0.0
            occ_delta = occ_cur - occ_prev

            # ADR/RevPAR: media semplice dei mesi disponibili come proxy
            def _mean(k):
                v = pd.to_numeric(ydf[k], errors="coerce").dropna()
                v = v[v != 0]
                return float(v.mean()) if len(v) else 0.0
            adr_cur   = _mean("adr_cur")
            adr_prev  = _mean("adr_prev")
            adr_delta = adr_cur - adr_prev

            rpar_cur   = _mean("revpar_cur")
            rpar_prev  = _mean("revpar_prev")
            rpar_delta = rpar_cur - rpar_prev

            notti_cur   = float(pd.to_numeric(ydf["nights_sold_cur"], errors="coerce").sum())
            notti_prev  = float(pd.to_numeric(ydf["nights_sold_prev"], errors="coerce").sum())
            notti_delta = notti_cur - notti_prev

            # Mappa verso renderer
            kpi_cur_y = {
                "Revenue":       revenue_cur,
                "Occupazione":   occ_cur,
                "Notti vendute": notti_cur,
                "ADR":           adr_cur,
                "RevPAR":        rpar_cur,
            }
            kpi_delta_y = {
                "Revenue":       revenue_delta,
                "Occupazione":   occ_delta,
                "Notti vendute": notti_delta,
                "ADR":           adr_delta,
                "RevPAR":        rpar_delta,
            }

            render_pickup_strip(kpi_cur_y, kpi_delta_y, titolo=f"Pick-up Giornaliero — {year_sel}")

# ─────────────────────────────────────────────────────────────────────────────
# TABELLINA • Movimenti di pick-up (oggi vs ieri) — append-only
# Mostra dove si sono mossi € e notti per property × mese di soggiorno
# ─────────────────────────────────────────────────────────────────────────────
from datetime import date
import pandas as pd
import numpy as np

try:
    from modules.pickup_engine import pickup_between
except Exception as _e:
    pickup_between = None
    st.warning("Pick-up Engine non disponibile. Aggiungi modules/pickup_engine.py al repo.")

DB_PATH = ".devlab/data/snapshots.db" if "DB_PATH" not in globals() else DB_PATH  # riusa se già definito

with st.container(border=True):
    st.caption("Tabella • Movimenti di pick-up (oggi vs ieri)")

    # Controlli (indipendenti da quelli delle strisce)
    c1, c2, c3, c4 = st.columns([1.6, 1.6, 1.6, 1.2], gap="large")
    with c1:
        as_of_tbl = st.date_input("As-of", value=date.today(), key="asof_moves")
    with c2:
        prev_auto_tbl = st.checkbox("Precedente automatico", value=True, key="auto_prev_moves")
    with c3:
        prev_tbl = None if prev_auto_tbl else st.date_input("Confronta con", value=date.today(), key="prev_moves")
    with c4:
        only_changes = st.checkbox("Solo variazioni ≠ 0", value=True)

    c5, c6 = st.columns([2, 2], gap="large")
    with c5:
        prop_tbl = st.text_input("Property (vuoto = tutte)", value="", key="prop_moves")
    with c6:
        order_by_rev = st.checkbox("Ordina per Δ Revenue desc", value=True)

    if pickup_between is None:
        st.stop()

    dfm = pickup_between(
        DB_PATH,
        as_of_current=as_of_tbl,
        as_of_prev=prev_tbl,
        property_name=(prop_tbl or None)
    )

    if dfm.empty:
        st.info("Nessuno snapshot per la data selezionata. Importa prima i forecast con otb_snapshots.py.")
    else:
        # Etichetta mese
        dfm["Mese"] = pd.to_datetime(
            dfm["stay_year"].astype(int).astype(str) + "-" + dfm["stay_month"].astype(int).astype(str) + "-01"
        ).dt.strftime("%b %Y").str.capitalize()

        # Selezione colonne: valori correnti + Δ (assolute)
        view = pd.DataFrame({
            "Property": dfm["property"].astype(str),
            "Mese": dfm["Mese"],
            "Revenue (cur)": pd.to_numeric(dfm["revenue_cur"], errors="coerce").fillna(0.0),
            "Δ Revenue": pd.to_numeric(dfm["revenue_delta"], errors="coerce").fillna(0.0),
            "Notti (cur)": pd.to_numeric(dfm["nights_sold_cur"], errors="coerce").fillna(0.0),
            "Δ Notti": pd.to_numeric(dfm["nights_sold_delta"], errors="coerce").fillna(0.0),
            "Occ % (cur)": pd.to_numeric(dfm["occupancy_pct_cur"], errors="coerce").fillna(0.0),
            "Δ Occ p.p.": pd.to_numeric(dfm["occupancy_pct_delta"], errors="coerce").fillna(0.0),
            "ADR (cur)": pd.to_numeric(dfm["adr_cur"], errors="coerce").fillna(0.0),
            "Δ ADR": pd.to_numeric(dfm["adr_delta"], errors="coerce").fillna(0.0),
            "RevPAR (cur)": pd.to_numeric(dfm["revpar_cur"], errors="coerce").fillna(0.0),
            "Δ RevPAR": pd.to_numeric(dfm["revpar_delta"], errors="coerce").fillna(0.0),
        })

        if only_changes:
            mask = (view[["Δ Revenue","Δ Notti","Δ Occ p.p.","Δ ADR","Δ RevPAR"]] != 0).any(axis=1)
            view = view.loc[mask]

        # Ordinamento
        if order_by_rev:
            view = view.sort_values(["Δ Revenue","Property","Mese"], ascending=[False, True, True])
        else:
            view = view.sort_values(["Property","Mese"], ascending=[True, True])

        # Totale riga finale (se tutte le property)
        if prop_tbl.strip() == "":
            totals = pd.Series({
                "Property": "TOTALE",
                "Mese": "",
                "Revenue (cur)": view["Revenue (cur)"].sum(),
                "Δ Revenue": view["Δ Revenue"].sum(),
                "Notti (cur)": view["Notti (cur)"].sum(),
                "Δ Notti": view["Δ Notti"].sum(),
                "Occ % (cur)": 0.0,         # non sommiamo percentuali
                "Δ Occ p.p.": view["Δ Occ p.p."].mean(),  # proxy: media delle variazioni in p.p.
                "ADR (cur)": view["ADR (cur)"].mean(),    # proxy
                "Δ ADR": view["Δ ADR"].mean(),            # proxy
                "RevPAR (cur)": view["RevPAR (cur)"].mean(),  # proxy
                "Δ RevPAR": view["Δ RevPAR"].mean(),          # proxy
            })
            view = pd.concat([view, totals.to_frame().T], ignore_index=True)

        # Formattazioni display
        fmt_eur = lambda s: s.map(lambda x: _fmt_eur(float(x)))
        fmt_int = lambda s: s.map(lambda x: _fmt_th(int(x)))
        fmt_pct = lambda s: s.map(lambda x: _fmt_pct(float(x)))

        disp = view.copy()
        disp["Revenue (cur)"] = fmt_eur(disp["Revenue (cur)"])
        disp["Δ Revenue"]     = fmt_eur(disp["Δ Revenue"])
        disp["Notti (cur)"]   = fmt_int(disp["Notti (cur)"])
        disp["Δ Notti"]       = fmt_int(disp["Δ Notti"])
        disp["Occ % (cur)"]   = fmt_pct(disp["Occ % (cur)"])
        # Δ Occ espresso in punti percentuali, usiamo _fmt_pct su valore assoluto (coerente visivamente)
        disp["Δ Occ p.p."]    = fmt_pct(disp["Δ Occ p.p."])
        disp["ADR (cur)"]     = fmt_eur(disp["ADR (cur)"])
        disp["Δ ADR"]         = fmt_eur(disp["Δ ADR"])
        disp["RevPAR (cur)"]  = fmt_eur(disp["RevPAR (cur)"])
        disp["Δ RevPAR"]      = fmt_eur(disp["Δ RevPAR"])

        # Visualizzazione
        st.dataframe(
            disp,
            use_container_width=True,
            hide_index=True
        )

        # Nota metodologica
        st.markdown(
            "<small>Note: Δ su ADR/RevPAR/Occ annidate al mese; per aggregazioni a livello più alto useremo pesi appropriati nei prossimi step.</small>",
            unsafe_allow_html=True
        )

st.title("DevLab – Kross Dashboard – Multi Struttura [DEV]")

# -----------------------------------------------------------------------------
# CONFIG & STATE
# -----------------------------------------------------------------------------
CFG = load_config("config.yaml")
ROOMS_DEFAULT = int(CFG.get("rooms_default", 5))
ROOMS_MAP: dict = CFG.get("rooms_per_property", {})

CURRENCY = CFG.get("currency_symbol", "€")

today = datetime.now()
st.session_state.setdefault("active_year", today.year)
st.session_state.setdefault("active_month", today.month)
st.session_state.setdefault("datasets", {})

PROPERTIES = ["Lavagnini My Place", "La Terrazza di Jenny"]
YEARS = [2024, 2025]

# -----------------------------------------------------------------------------
# SIDEBAR: Selettori + Uploader
# -----------------------------------------------------------------------------
st.sidebar.header("Carica i dati")
prop_sel = st.sidebar.selectbox("Struttura", options=PROPERTIES, index=0)
year_sel = st.sidebar.selectbox("Anno", options=YEARS, index=YEARS.index(today.year) if today.year in YEARS else 0)

upl = st.sidebar.file_uploader(f"File {prop_sel} – {year_sel}", type=["xlsx"], key=f"uploader_{prop_sel}_{year_sel}")
col_sb_a, col_sb_b = st.sidebar.columns(2)
with col_sb_a:
    if st.button("Carica file selezionato", use_container_width=True):
        if upl is None:
            st.sidebar.warning("Seleziona un file prima di caricare.")
        else:
            data = upl.read()
            df = normalize_wide_excel(io.BytesIO(data), CFG, prop_sel)
            df = df[df["year"] == year_sel].copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = df
            st.sidebar.success(f"Caricato: {prop_sel} – {year_sel} ({len(df)} righe)")
with col_sb_b:
    SHOW_DEMO = True
    if SHOW_DEMO and st.button("Usa file demo", use_container_width=True):
        demo_map = {
            ("Lavagnini My Place", 2024): "/mnt/data/Lavagnini_Forecast_01012024_31122024.xlsx",
            ("Lavagnini My Place", 2025): "/mnt/data/Lavagnini_Forecast_01012025_31122025.xlsx",
            ("La Terrazza di Jenny", 2024): "/mnt/data/La_Terrazza_Forecast_01092024_31122024.xlsx",
            ("La Terrazza di Jenny", 2025): "/mnt/data/La_Terrazza_Forecast_01012025_31122025.xlsx",
        }
        path = demo_map.get((prop_sel, year_sel))
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                df = normalize_wide_excel(io.BytesIO(f.read()), CFG, prop_sel)
            df = df[df["year"] == year_sel].copy()
            st.session_state["datasets"][(prop_sel, year_sel)] = df
            st.sidebar.success(f"Demo caricata: {prop_sel} – {year_sel} ({len(df)} righe)")
        else:
            st.sidebar.warning("Demo non disponibile per la combinazione scelta.")

st.sidebar.markdown("---")
if st.sidebar.button("Svuota caricamenti"):
    st.session_state["datasets"].clear()
    st.sidebar.info("Archivio file svuotato.")

# -----------------------------------------------------------------------------
# ASSEMBLA DF GLOBALE
# -----------------------------------------------------------------------------
if not st.session_state["datasets"]:
    st.warning("Carica almeno un file (Struttura + Anno).")
    st.stop()

df_all = pd.concat(st.session_state["datasets"].values(), ignore_index=True)
properties = sorted(df_all["property"].dropna().unique().tolist())

st.sidebar.markdown("---")
view_mode = st.sidebar.radio("Vista", options=["Singola struttura", "Aggregata"], index=0)
if view_mode == "Singola struttura":
    prop_view = st.sidebar.selectbox("Seleziona struttura per l'analisi", options=properties, index=0)
    props_to_use = [prop_view]
else:
    props_to_use = st.sidebar.multiselect("Seleziona strutture da aggregare", options=properties, default=properties)

df_view = df_all[df_all["property"].isin(props_to_use)].copy()
if df_view.empty:
    st.warning("Nessun dato per la selezione corrente."); st.stop()

# -----------------------------------------------------------------------------
# NAV UTILS MESE
# -----------------------------------------------------------------------------
def _month_labels(y: int, m: int):
    it = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"]
    curr = f"{it[m-1]} {y}"
    pm, py = (12, y-1) if m == 1 else (m-1, y)
    nm, ny = (1, y+1) if m == 12 else (m+1, y)
    return curr, f"{it[pm-1]} {py}", f"{it[nm-1]} {ny}"

def go_prev():  # mese--
    m = st.session_state["active_month"]; y = st.session_state["active_year"]
    if m == 1: st.session_state["active_month"], st.session_state["active_year"] = 12, y-1
    else:      st.session_state["active_month"] = m-1

def go_next():  # mese++
    m = st.session_state["active_month"]; y = st.session_state["active_year"]
    if m == 12: st.session_state["active_month"], st.session_state["active_year"] = 1, y+1
    else:       st.session_state["active_month"] = m+1

active_y = st.session_state["active_year"]
active_m = st.session_state["active_month"]
curr_label, prev_label, next_label = _month_labels(active_y, active_m)

# -----------------------------------------------------------------------------
# KPI MESE (formattazioni + calcolo robusto)
# -----------------------------------------------------------------------------
def _fmt_eur(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{CURRENCY} {s}"
def _fmt_pct(x: float) -> str:
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}%"
def _fmt_th(n: int) -> str:
    return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

def _first_sum(df: pd.DataFrame, cands: list[str]) -> float:
    if df is None or df.empty: return 0.0
    for c in cands:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce").sum()
            if pd.notna(v): return float(v)
    return 0.0

def _first_mean(df: pd.DataFrame, cands: list[str]) -> float:
    if df is None or df.empty: return 0.0
    for c in cands:
        if c in df.columns:
            v = pd.to_numeric(df[c], errors="coerce").mean()
            if pd.notna(v): return float(v)
    return 0.0

def _rooms_avail_fallback(df_month_like: pd.DataFrame, year: int, month: int) -> float:
    """Se mancano 'rooms_available', calcola: camere_per_struttura × giorni_del_mese, sommato sulle strutture presenti."""
    if df_month_like is None or df_month_like.empty: 
        return 0.0
    days = pd.Period(f"{year}-{month:02d}").days_in_month
    props = (df_month_like["property"].dropna().unique().tolist() 
             if "property" in df_month_like.columns else [])
    if not props:  # se non ci sono proprietà nel DF (edge case), usa selezione corrente se disponibile
        props = []
    total = 0.0
    for p in props:
        rooms = int(ROOMS_MAP.get(p, ROOMS_DEFAULT))
        total += rooms * days
    return float(total)

# Sottoinsiemi anno/mese corrente e stesso mese anno precedente
df_cur  = df_view[(df_view["year"] == active_y)     & (df_view["month"] == active_m)].copy()
df_prev = df_view[(df_view["year"] == active_y - 1) & (df_view["month"] == active_m)].copy()

# Notti vendute (somma) – prova più nomi di colonna
sold_nights    = int(round(_first_sum(df_cur,  ["occupied","notti","nights","rooms_sold","sold_nights"])))
sold_nights_py = int(round(_first_sum(df_prev, ["occupied","notti","nights","rooms_sold","sold_nights"])))

# Camere disponibili – usa la colonna se c'è, altrimenti fallback da config
rooms_avail    = _first_sum(df_cur,  ["rooms_available","rooms_avail","camere_disponibili"])
rooms_avail_py = _first_sum(df_prev, ["rooms_available","rooms_avail","camere_disponibili"])
if rooms_avail == 0.0:
    rooms_avail    = _rooms_avail_fallback(df_cur,  active_y,     active_m)
if rooms_avail_py == 0.0:
    rooms_avail_py = _rooms_avail_fallback(df_prev, active_y - 1, active_m)

# Revenue (somma), ADR/RevPAR (media giornaliera)
revenue    = _first_sum(df_cur,  ["revenue","totale_revenue","ricavi"])
revenue_py = _first_sum(df_prev, ["revenue","totale_revenue","ricavi"])
# --- ADR: prima formula (Revenue / Notti vendute), altrimenti media colonna se disponibile
adr_calc    = (revenue / sold_nights)       if sold_nights    > 0 else 0.0
adr_col     = _first_mean(df_cur,  ["adr","ADR"])
adr         = adr_calc if adr_calc > 0 else (adr_col or 0.0)

adr_py_calc = (revenue_py / sold_nights_py) if sold_nights_py > 0 else 0.0
adr_py_col  = _first_mean(df_prev, ["adr","ADR"])
adr_py      = adr_py_calc if adr_py_calc > 0 else (adr_py_col or 0.0)

# --- RevPAR: prima formula (Revenue / Camere disponibili), altrimenti media colonna se disponibile
revpar_calc    = (revenue / rooms_avail)       if rooms_avail    > 0 else 0.0
revpar_col     = _first_mean(df_cur,  ["revpar","RevPAR"])
revpar         = revpar_calc if revpar_calc > 0 else (revpar_col or 0.0)

revpar_py_calc = (revenue_py / rooms_avail_py) if rooms_avail_py > 0 else 0.0
revpar_py_col  = _first_mean(df_prev, ["revpar","RevPAR"])
revpar_py      = revpar_py_calc if revpar_py_calc > 0 else (revpar_py_col or 0.0)

# Occupazione
occ_pct    = (sold_nights    / rooms_avail    * 100.0) if rooms_avail    > 0 else 0.0
occ_pct_py = (sold_nights_py / rooms_avail_py * 100.0) if rooms_avail_py > 0 else 0.0

kpi_header = {
    "Revenue": _fmt_eur(revenue),
    "Occupazione": _fmt_pct(occ_pct),
    "Notti vendute": _fmt_th(sold_nights),
    "ADR": _fmt_eur(adr),
    "RevPAR": _fmt_eur(revpar),
}
deltas_header = {
    "Revenue": revenue - revenue_py,
    "Occupazione": occ_pct - occ_pct_py,
    "Notti vendute": sold_nights - sold_nights_py,
    "ADR": adr - adr_py,
    "RevPAR": revpar - revpar_py,
}

# -----------------------------------------------------------------------------
# GRIGLIA 5 COLONNE COERENTE (riutilizzata da header e KPI)
# -----------------------------------------------------------------------------
def _five_slots():
    """Unica griglia condivisa: [2,1,3,1,2] con gap large. Garantisce allineamento 1:1 tra righe."""
    return st.columns([2, 1, 3, 1, 2], gap="large")

def render_year_header_1547(year_label: int):
    """
    Header ANNO: titolo centrato e pulsanti SX/DX con etichette sotto i bottoni,
    identico alla struttura della navigazione MESE (usa _five_slots()).
    Ritorna: {"prev_clicked": bool, "next_clicked": bool}
    """
    c1, c2, c3, c4, c5 = _five_slots()  # stessa griglia 2–1–3–1–2
    prev_year = year_label - 1
    next_year = year_label + 1

    with c1:  # pulsante sinistro + label anno precedente
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        prev_clicked = st.button("◀", key="yh_prev", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{prev_year}</div>', unsafe_allow_html=True)

    with c3:  # titolo centrale su due righe (come mese)
        st.markdown(
            f"""
            <div class="mh-center" style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:110px;">
              <p class="mh-month" style="font-size:28px; line-height:1.1; font-weight:700;">Anno {year_label}</p>
              <div class="mh-sub">(anno di comparazione: {year_label-1})</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c5:  # pulsante destro + label anno successivo
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        next_clicked = st.button("▶", key="yh_next", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{next_year}</div>', unsafe_allow_html=True)

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

    # -----------------------------------------------------------------------------
# STRISCIA ANNO – KPI (stessa grafica/struttura della striscia MESE)
# -----------------------------------------------------------------------------
def _compute_year_kpis(df_all_like: pd.DataFrame, year: int) -> tuple[dict, dict]:
    """Calcola KPI annuali + delta YoY sullo stesso perimetro di strutture selezionate."""
    import calendar
    df_y  = df_all_like[df_all_like["year"] == year].copy()
    df_py = df_all_like[df_all_like["year"] == year - 1].copy()

    # --- helper robusti su colonne possibili ---
    def _sum_first(df: pd.DataFrame, cands: list[str]) -> float:
        if df is None or df.empty: return 0.0
        for c in cands:
            if c in df.columns:
                try: return float(df[c].sum())
                except: pass
        return 0.0

    def _mean_first(df: pd.DataFrame, cands: list[str]) -> float:
        if df is None or df.empty: return 0.0
        for c in cands:
            if c in df.columns:
                try: return float(df[c].mean())
                except: pass
        return 0.0

    # Fallback camere disponibili anno (se mancano rooms_available nel file)
    def _fallback_rooms_avail_year(df_year_like: pd.DataFrame, default_rooms: int) -> float:
        if df_year_like is None or df_year_like.empty: return 0.0
        tot = 0.0
        props = df_year_like["property"].dropna().unique().tolist() if "property" in df_year_like.columns else [None]
        for p in props:
            dfp = df_year_like if p is None else df_year_like[df_year_like["property"] == p]
            rooms = int(ROOMS_MAP.get(p, default_rooms)) if p is not None else int(default_rooms)
            for _, r in dfp[["year", "month"]].drop_duplicates().iterrows():
                tot += rooms * calendar.monthrange(int(r["year"]), int(r["month"]))[1]
        return float(tot)

    # --- KPI anno corrente ---
    sold_y   = int(_sum_first(df_y,  ["occupied","sold_nights","rooms_sold","nights","notti"]))
    rooms_y  = _sum_first(df_y, ["rooms_available","rooms_avail","camere_disponibili"]) or _fallback_rooms_avail_year(df_y, ROOMS_DEFAULT)
    rev_y    = _sum_first(df_y,  ["revenue","totale_revenue","ricavi"])
    adr_y    = _mean_first(df_y, ["adr"])
    rpar_y   = _mean_first(df_y, ["revpar"])
    occ_y    = (sold_y / rooms_y * 100.0) if rooms_y > 0 else 0.0

    # --- KPI anno precedente (per delta YoY) ---
    sold_py  = int(_sum_first(df_py,  ["occupied","sold_nights","rooms_sold","nights","notti"]))
    rooms_py = _sum_first(df_py, ["rooms_available","rooms_avail","camere_disponibili"]) or _fallback_rooms_avail_year(df_py, ROOMS_DEFAULT)
    rev_py   = _sum_first(df_py,  ["revenue","totale_revenue","ricavi"])
    adr_py   = _mean_first(df_py, ["adr"])
    rpar_py  = _mean_first(df_py, ["revpar"])
    occ_py   = (sold_py / rooms_py * 100.0) if rooms_py > 0 else 0.0

    # --- formattazioni coerenti con la striscia mese ---
    def _fmt_eur(x: float) -> str:
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{CURRENCY} {s}"

    def _fmt_pct(x: float) -> str:
        s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s}%"

    def _fmt_th(n: int) -> str:
        return f"{n:,}".replace(",", "X").replace(".", ",").replace("X", ".")

    kpi_year = {
        "Revenue":      _fmt_eur(rev_y),
        "Occupazione":  _fmt_pct(occ_y),
        "Notti vendute":_fmt_th(sold_y),
        "ADR":          _fmt_eur(adr_y),
        "RevPAR":       _fmt_eur(rpar_y),
    }
    deltas_year = {
        "Revenue":       rev_y  - rev_py,
        "Occupazione":   occ_y  - occ_py,
        "Notti vendute": sold_y - sold_py,
        "ADR":           adr_y  - adr_py,
        "RevPAR":        rpar_y - rpar_py,
    }
    return kpi_year, deltas_year


def render_year_kpis_1547(kpi: dict, deltas: dict):
    """UI della striscia dati ANNO – identica alla striscia dati MESE (stesse classi, stessi layout)."""
    # Stessi stili della striscia mese (li includiamo anche qui perché la barra anno è renderizzata prima)
    st.markdown("""
<style>
.kpi-col{ width:100%; display:flex; flex-direction:column; align-items:center; }
.kpi-label{ font-size:14px; color:#6b7280; margin-bottom:6px; white-space:nowrap; }
.kpi-value{ font-size:36px; font-weight:400; color:#111827; line-height:1.15; white-space:nowrap; } /* no bold */
.kpi-pill{ display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border-radius:999px;
           font-size:13px; font-weight:600; margin-top:8px; }
.kpi-pill.up{ background:#ecfdf5; color:#16a34a; }
.kpi-pill.down{ background:#fef2f2; color:#dc2626; }
</style>
""", unsafe_allow_html=True)

    def pill(delta: float) -> str:
        if delta is None: return ""
        cls  = "up" if delta >= 0 else "down"
        icon = "↑" if delta >= 0 else "↓"
        val  = f"{delta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span class="kpi-pill {cls}">{icon} {val}</span>'

    # Identica griglia: [2,1,3,1,2]
    col_rev, col_occ, col_notti, col_adr, col_rpar = _five_slots()

    with col_rev:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Revenue anno</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Revenue","–")}</div>{pill(deltas.get("Revenue"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_occ:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Occupazione</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Occupazione","–")}</div>{pill(deltas.get("Occupazione"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_notti:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">Notti vendute</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("Notti vendute","–")}</div>{pill(deltas.get("Notti vendute"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_adr:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">ADR medio</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("ADR","–")}</div>{pill(deltas.get("ADR"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_rpar:
        st.markdown('<div class="kpi-col">', unsafe_allow_html=True)
        st.markdown('<div class="kpi-label">RevPAR medio</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-value">{kpi.get("RevPAR","–")}</div>{pill(deltas.get("RevPAR"))}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    """Navigazione ANNO su 5 colonne, identica alla barra mese."""
    prev_year = year_label - 1
    next_year = year_label + 1

    # usa la stessa griglia condivisa
    c1, c2, c3, c4, c5 = _five_slots()

    # SX: pulsante + label anno precedente (verde scuro bold)
    with c1:
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        prev_clicked = st.button("◀", key="yh_prev", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{prev_year}</div>', unsafe_allow_html=True)

       # CENTRO: anno corrente (grande, centrato anche verticalmente) + sottotitolo identico alla barra mese
    with c3:
        compare_year = year_label - 1
        st.markdown(
            f'''
<div class="mh-center" style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:110px;">
  <p class="mh-month" style="font-size:28px; line-height:1.1; font-weight:700;">Anno {year_label}</p>
  <div class="mh-sub">(anno di comparazione: {compare_year})</div>
</div>
''',
            unsafe_allow_html=True
        )

    # DX: pulsante + label anno successivo (verde scuro bold)
    with c5:
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        next_clicked = st.button("▶", key="yh_next", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#15803d; font-weight:700;">{next_year}</div>', unsafe_allow_html=True)

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# -----------------------------------------------------------------------------
# STRISCIA MESE – Navigazione (5 colonne)
# -----------------------------------------------------------------------------
def render_month_header_1547(month_label: str, prev_month_label: str, next_month_label: str, compare_year: int):
    c1, c2, c3, c4, c5 = _five_slots()

    with c1:  # pulsante sinistro + label mese precedente
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        prev_clicked = st.button("◀", key="mh_prev", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#166534; font-weight:700;">{prev_month_label}</div>', unsafe_allow_html=True)

    with c3:
        st.markdown(
        f'''
        <div class="mh-center" style="display:flex; flex-direction:column; justify-content:center; align-items:center; height:110px;">
        <p class="mh-month" style="font-size:28px; line-height:1.1; font-weight:700;">{month_label}</p>
        <div class="mh-sub">(anno di comparazione: {compare_year})</div>
        </div>
        ''',
        unsafe_allow_html=True
    )

    with c5:  # pulsante destro + label mese successivo
        st.markdown('<div class="mh-btn">', unsafe_allow_html=True)
        next_clicked = st.button("▶", key="mh_next", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="mh-under" style="color:#166534; font-weight:700;">{next_month_label}</div>', unsafe_allow_html=True)

    return {"prev_clicked": prev_clicked, "next_clicked": next_clicked}

# -----------------------------------------------------------------------------
# STRISCIA MESE – KPI (5 colonne allineate all’header)
# -----------------------------------------------------------------------------
def render_month_kpis_1547(kpi: dict[str, str], deltas: dict[str, float]):
    # --- CSS grid a 5 colonne fisse: 2fr 1fr 3fr 1fr 2fr ---
    st.markdown("""
<style>
.kpi-row {
  display: grid;
  grid-template-columns: 2fr 1fr 3fr 1fr 2fr;
  column-gap: 64px;        /* allinea al gap "large" dell'header */
  align-items: start;
}
.kpi-box {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;   /* centra il contenuto nel proprio slot */
}
.kpi-label { font-size: 14px; color: #6b7280; margin-bottom: 6px; white-space: nowrap; }
.kpi-value { font-size: 36px; font-weight: 400; color: #111827; line-height: 1.15; white-space: nowrap; }
.kpi-pill  { display: inline-flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 999px;
             font-size: 13px; font-weight: 600; margin-top: 8px; }
.kpi-pill.up   { background: #ecfdf5; color: #16a34a; }
.kpi-pill.down { background: #fef2f2; color: #dc2626; }
</style>
""", unsafe_allow_html=True)

    # helper per la pill del delta
    def pill(delta: float) -> str:
        if delta is None:
            return ""
        is_up = delta >= 0
        cls = "up" if is_up else "down"
        icon = "↑" if is_up else "↓"
        val = f"{delta:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f'<span class="kpi-pill {cls}">{icon} {val}</span>'

    # HTML della riga KPI: 5 celle -> 1) Revenue  2) Occupazione  3) Notti vendute  4) ADR  5) RevPAR
    html = f"""
<div class="kpi-row">
  <div class="kpi-box">
    <div class="kpi-label">Revenue mese</div>
    <div class="kpi-value">{kpi.get("Revenue","–")}</div>
    {pill(deltas.get("Revenue"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">Occupazione</div>
    <div class="kpi-value">{kpi.get("Occupazione","–")}</div>
    {pill(deltas.get("Occupazione"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">Notti vendute</div>
    <div class="kpi-value">{kpi.get("Notti vendute","–")}</div>
    {pill(deltas.get("Notti vendute"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">ADR medio</div>
    <div class="kpi-value">{kpi.get("ADR","–")}</div>
    {pill(deltas.get("ADR"))}
  </div>

  <div class="kpi-box">
    <div class="kpi-label">RevPAR medio</div>
    <div class="kpi-value">{kpi.get("RevPAR","–")}</div>
    {pill(deltas.get("RevPAR"))}
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    st.divider()
    
# -----------------------------------------------------------------------------
# RENDER PAGINA
# -----------------------------------------------------------------------------
# === NAVIGAZIONE ANNO (prima della sezione mese) ===
yhdr = render_year_header_1547(active_y)

# Cambio anno: aggiorna anche il mese alla mensilità corrente del calendario, mantenendo lo stesso anno interrogato
if yhdr.get("prev_clicked"):
    st.session_state["active_year"] = active_y - 1
    st.session_state["active_month"] = datetime.now().month   # mese corrente, ma del nuovo anno
    st.rerun()
if yhdr.get("next_clicked"):
    st.session_state["active_year"] = active_y + 1
    st.session_state["active_month"] = datetime.now().month   # mese corrente, ma del nuovo anno
    st.rerun()
# === STRISCIA DATI – ANNO (riuso del renderer MESE per allineamento pixel-perfect) ===
# === STRISCIA DATI – ANNO (riuso renderer MESE) ===
kpi_year, deltas_year = _compute_year_kpis(df_view, active_y)
render_month_kpis_1547(kpi_year, deltas_year)
hdr = render_month_header_1547(
    month_label=curr_label,
    prev_month_label=prev_label,
    next_month_label=next_label,
    compare_year=active_y - 1
)
if hdr.get("prev_clicked"): go_prev(); st.rerun()
if hdr.get("next_clicked"): go_next(); st.rerun()

render_month_kpis_1547(kpi_header, deltas_header)

# -----------------------------------------------------------------------------
# (segue tutto il resto della pagina: KPI mensili, tabelle, grafici…)
# -----------------------------------------------------------------------------
