#!/usr/bin/env bash
# ============================================================
#  ERP AI Agent Testing Suite – One-Click Installer & Launcher
# ============================================================
#  Works on Linux / macOS / WSL / Git Bash
#  Double-click or run:  ./install_and_run.sh
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "  ERP AI Agent Testing Suite – Installer"
echo "============================================================"
echo ""

# 1. Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 is required. Please install Python 3.9+ and try again."
    exit 1
fi
PYTHON=$(command -v python3)
echo "✅ Python found: $($PYTHON --version)"

# 2. Create virtual environment
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    $PYTHON -m venv venv
fi
source venv/bin/activate
echo "✅ Virtual environment ready"

# 3. Install dependencies
echo "→ Installing Python packages..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ Dependencies installed"

# 4. Configure .env
ENV_FILE="config/.env"
if [ ! -f "$ENV_FILE" ]; then
    cp config/.env.example "$ENV_FILE"
    echo ""
    echo "------------------------------------------------------------"
    echo "  First-time setup: API Key configuration"
    echo "------------------------------------------------------------"
    echo ""
    echo "The agent can run in two modes:"
    echo "  1. MOCK  – deterministic rules (no API key needed)"
    echo "  2. LLM   – real Large Language Model (needs your API key)"
    echo ""
    read -p "Do you want to use a real LLM now? (y/N): " USE_LLM
    if [[ "$USE_LLM" =~ ^[Yy]$ ]]; then
        read -p "Enter your OpenAI-compatible API key: " API_KEY
        read -p "Base URL [https://api.openai.com/v1]: " BASE_URL
        BASE_URL=${BASE_URL:-https://api.openai.com/v1}
        read -p "Model name [gpt-4o-mini]: " MODEL
        MODEL=${MODEL:-gpt-4o-mini}

        # Write the .env file safely
        cat > "$ENV_FILE" <<EOF
OPENAI_API_KEY=$API_KEY
OPENAI_BASE_URL=$BASE_URL
OPENAI_MODEL=$MODEL
AGENT_MODE=llm
EOF
        echo "✅ LLM mode configured. Key saved to config/.env (keep this private!)"
    else
        sed -i 's/AGENT_MODE=.*/AGENT_MODE=mock/' "$ENV_FILE" 2>/dev/null || \
        echo "AGENT_MODE=mock" >> "$ENV_FILE"
        echo "✅ Running in MOCK mode (no API key required)."
    fi
else
    echo "✅ Existing config/.env found – using it."
fi

echo ""
echo "============================================================"
echo "  What do you want to launch?"
echo "============================================================"
echo "  1) Web UI  (recommended – traces, history, shareable links)"
echo "  2) CLI     (classic terminal agent)"
echo ""
read -p "Choice [1]: " CHOICE
CHOICE=${CHOICE:-1}

if [ "$CHOICE" = "2" ]; then
    echo ""
    echo "Launching CLI agent... (type 'help' for samples, 'quit' to exit)"
    echo ""
    python app/erp_agent.py
else
    echo ""
    echo "Starting Web UI on http://localhost:8501"
    echo "  • Every request gets a unique ID and shareable link"
    echo "  • Full tool traces are shown for each request"
    echo "  • Prompt history is saved in data/request_history.json"
    echo ""
    echo "Press Ctrl+C to stop the server."
    echo ""
    streamlit run app/ui.py --server.headless true
fi
