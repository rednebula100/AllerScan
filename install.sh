#!/usr/bin/env bash
set -e

echo "============================================"
echo "  AllerScan Setup"
echo "============================================"
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 was not found."
    echo "        Install Python 3.10+ from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "[ERROR] Python 3.10+ is required. Found: $PY_VERSION"
    exit 1
fi
echo "[OK] Python $PY_VERSION detected."
echo

echo "[*] Installing dependencies..."
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt
echo

echo "[*] Preparing data directories..."
mkdir -p data/presets data/meals data/symptoms

echo
echo "============================================"
echo "  Setup complete!"
echo "  Start AllerScan with:"
echo
echo "    export NEIS_API_KEY=\"your_key\""
echo "    export MFDS_API_KEY=\"your_key\"   # optional"
echo "    python3 main.py"
echo "============================================"
