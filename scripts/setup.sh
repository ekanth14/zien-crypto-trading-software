#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   ZIEN CRYPTO // QUANTITATIVE TERMINAL SETUP"
echo "=========================================================="

python3 -c "import sys; print(f'Python detected: {sys.version_info.major}.{sys.version_info.minor}')"

mkdir -p cryptoscope/static cryptoscope/tests work/runtime work/backups

if command -v ollama &>/dev/null; then
    if ollama list | grep -q "laya-crypto"; then
        echo "[OK] Ollama model 'laya-crypto:latest' is registered and ready."
    else
        echo "[INFO] Creating Ollama model 'laya-crypto:latest' from Modelfile..."
        ollama create laya-crypto:latest -f Modelfile
    fi
else
    echo "[WARN] Ollama CLI not detected. Rule-based fallback active."
fi

python3 cryptoscope/manage.py doctor

echo "=========================================================="
echo "   Setup complete! Launch with:"
echo "   python3 server.py --port 8900"
echo "=========================================================="
