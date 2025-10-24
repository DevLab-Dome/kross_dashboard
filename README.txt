# DevLab – Kross Dashboard (MACOS)

## Avvio rapido (dentro la cartella del progetto)
1. Apri Terminale e vai nella cartella scaricata:
   cd ~/Downloads/kross_dashboard    # oppure la cartella dove l'hai salvata

2. Crea/attiva ambiente virtuale:
   python3 -m venv .venv
   source .venv/bin/activate

3. Installa dipendenze:
   python3 -m pip install --upgrade pip
   python3 -m pip install -r requirements.txt

4. Avvia la webapp:
   python3 -m streamlit run streamlit_app.py

5. Nel browser, carica due file Excel (Storico 2024 e Corrente 2025).

## Note
- Le righe "Totale mese" vengono ignorate automaticamente.
- Le medie ADR/RevPAR sono calcolate come media giornaliera; Revenue è la somma mensile; Occupazione = Notti vendute / (Camere nominali × Giorni).
- Il numero di camere nominali è preso dalla colonna "Unità" (mode del mese); se assente, usa `rooms_default` in config.yaml.
Staging OK — test del deploy automatico.
