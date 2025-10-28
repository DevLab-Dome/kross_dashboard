# Changelog

## v0.3.4 — 2025-10-28
### Added
- **Striscia Dati – ANNO** allineata al renderer **MESE** (griglia 2–1–3–1–2) per layout identico.
- Navigazione **ANNO** con etichette SX/DX (verde + bold), titolo “Anno {YYYY}” e sottotitolo “(anno di comparazione: {YYYY-1})” uniformati allo stile MESE.

### Changed
- Riuso del componente `render_month_kpis_1547` per il rendering dei KPI **ANNO** (allineamento pixel-perfect).
- Sottotitoli ANNO aggiornati per coerenza tipografica con MESE (classi condivise).

### Removed
- **Divider** sotto le strisce di **navigazione** ANNO e MESE (restano i divider previsti sotto le strisce dati dove applicabile).

### Tech Notes
- KPI ANNO:  
  - **Occupazione** = notti vendute / camere disponibili anno × 100 (fallback camere da config quando `rooms_available` manca).  
  - **ADR** e **RevPAR** = **medie giornaliere**, non somme.  
  - **Δ YoY** = valore attuale − valore anno precedente; occupazione in **pp**; badge ↑ verde / ↓ rosso.
