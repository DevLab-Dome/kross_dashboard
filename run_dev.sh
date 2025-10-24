#!/usr/bin/env bash
set -e

# Go to the script's directory
cd "$(dirname "$0")"

echo "▶ Detecting Python 3..."
PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
  echo "❌ Nessun Python 3 trovato. Installa Python 3.11/3.13 da python.org e rilancia ./run_dev.sh"
  exit 1
fi
"$PY" -V || true

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "▶ Creo virtualenv .venv con: $PY"
  "$PY" -m venv .venv
fi

# Activate venv
echo "▶ Attivo virtualenv"
# shellcheck source=/dev/null
source .venv/bin/activate

echo "Python: $(python -V)"
echo "Path:   $(which python)"

# Ensure pip and core build tools
python -m ensurepip --upgrade || true
python -m pip install --upgrade pip setuptools wheel

# Install deps (fallback to explicit list if requirements fails on 3.13)
echo "▶ Installo dipendenze"
python -m pip install -r requirements.txt || python -m pip install streamlit pandas plotly openpyxl pyyaml python-dateutil

echo "▶ Avvio Streamlit"
exec python -m streamlit run streamlit_app.py
