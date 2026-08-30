#!/usr/bin/env bash
# ==============================================================================
# Ejiro Inspire Automation Stack - Complete 1-Click Installer
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
cat << "EOF"
  ______    _ _              _____                 _          
 |  ____|  (_) (_)          |_   _|               (_)         
 | |__      _| |_ _ __ ___    | |  _ __  ___ _ __  _ _ __ ___ 
 |  __|    | | | | '__/ _ \   | | | '_ \/ __| '_ \| | '__/ _ \
 | |____   | | | | | | (_) | _| |_| | | \__ \ |_) | | | |  __/
 |______|  | |_|_|_|  \___/ |_____|_| |_|___/ .__/|_|_|  \___|
          _/ |                              | |               
         |__/                               |_|               
   Autonomous Content, Research & Affiliate Monetization Stack
EOF
echo -e "${NC}"

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 1. Check System Prerequisites ─────────────────────────────────────────────
log_info "Step 1/6: Checking system prerequisites..."

check_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log_error "Required command '$1' is not installed."
        return 1
    fi
    return 0
}

MISSING_DEPS=0
for cmd in curl git python3 node npm; do
    if ! check_cmd "$cmd"; then
        MISSING_DEPS=1
    fi
done

if [ $MISSING_DEPS -eq 1 ]; then
    log_error "Please install the missing tools using your system package manager (apt, pacman, brew, etc.) and rerun ./install.sh"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
NODE_VERSION=$(node -v)
log_success "System prerequisites verified: Python $PYTHON_VERSION, Node $NODE_VERSION"

# ── 2. Setup / Verify Ollama & AI Engine ──────────────────────────────────────
log_info "Step 2/6: Checking Ollama local LLM engine..."

if ! command -v ollama >/dev/null 2>&1; then
    log_warn "Ollama is not installed on this system."
    read -p "Would you like to install Ollama automatically now? (y/N): " INSTALL_OLLAMA
    if [[ "$INSTALL_OLLAMA" =~ ^[Yy]$ ]]; then
        log_info "Installing Ollama via official installer..."
        curl -fsSL https://ollama.com/install.sh | sh
    else
        log_warn "Skipping Ollama installation. (Note: you can configure an external API like OpenAI or OpenRouter in .env)"
    fi
fi

if command -v ollama >/dev/null 2>&1; then
    log_success "Ollama is installed."
    
    # Ensure Ollama service is running
    if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        log_info "Starting Ollama service in background..."
        ollama serve >/dev/null 2>&1 &
        sleep 3
    fi

    # Check if user has any models installed
    INSTALLED_MODELS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
    if [ -z "$INSTALLED_MODELS" ]; then
        log_info "No Ollama models found. Pulling lightweight starter model 'qwen2.5:7b'..."
        ollama pull qwen2.5:7b || log_warn "Could not auto-pull model. You can run 'ollama pull <model>' anytime."
    else
        log_success "Detected installed Ollama models:"
        echo "$INSTALLED_MODELS" | sed 's/^/  - /'
    fi
fi

# ── 3. Setup Python Virtual Environment ───────────────────────────────────────
log_info "Step 3/6: Setting up Python virtual environment and dependencies..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    log_success "Created Python virtual environment (./venv)."
else
    log_info "Virtual environment already exists."
fi

source venv/bin/activate
pip install --upgrade pip -q
log_info "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt -q
log_success "Python dependencies installed."

log_info "Installing Playwright Chromium browser binary..."
playwright install chromium
log_success "Playwright Chromium ready."

# ── 4. Setup Custom Amazon Stealth Scraper ─────────────────────────────────────
log_info "Step 4/6: Setting up Custom Amazon Stealth Scraper microservice..."

cd "${PROJECT_DIR}/customamazonscraper"
if [ ! -d "node_modules" ]; then
    npm install --silent
    log_success "Node.js scraper dependencies installed."
else
    log_info "Node scraper dependencies already installed."
fi
cd "$PROJECT_DIR"

# ── 5. Setup Configuration & Environment ──────────────────────────────────────
log_info "Step 5/6: Configuring environment..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    log_success "Created .env from .env.example."
    log_warn "PLEASE EDIT .env with your CMS API_URL, API_TOKEN, and AMAZON_AFFILIATE_TAG before running!"
else
    log_info ".env already exists. Preserving your existing configuration."
fi

# ── 6. Setup Global CLI Command ───────────────────────────────────────────────
log_info "Step 6/6: Installing global 'ejiroinspire' CLI command..."

chmod +x "${PROJECT_DIR}/ejiroinspire"

INSTALL_GLOBAL=false
if [ -d "$HOME/.local/bin" ]; then
    ln -sf "${PROJECT_DIR}/ejiroinspire" "$HOME/.local/bin/ejiroinspire"
    INSTALL_GLOBAL=true
elif [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
    ln -sf "${PROJECT_DIR}/ejiroinspire" "/usr/local/bin/ejiroinspire"
    INSTALL_GLOBAL=true
fi

if [ "$INSTALL_GLOBAL" = true ]; then
    log_success "Installed global command: 'ejiroinspire'"
else
    log_warn "Could not link to ~/.local/bin. You can run './ejiroinspire start' directly from this directory."
fi

# ── Finished ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}================================================================${NC}"
echo -e "${GREEN}${BOLD}   🎉 Installation Complete! Ejiro Inspire Engine is Ready!     ${NC}"
echo -e "${GREEN}${BOLD}================================================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Verify/edit your ${CYAN}.env${NC} file (set your ${BOLD}API_URL${NC}, ${BOLD}API_TOKEN${NC}, ${BOLD}OLLAMA_MODEL${NC})."
echo -e "  2. Start the entire engine with one command:"
echo -e "     ${GREEN}${BOLD}ejiroinspire start${NC}   (or ${CYAN}./ejiroinspire start${NC})"
echo ""
echo -e "Useful Commands:"
echo -e "  - Check status:  ${CYAN}ejiroinspire status${NC}"
echo -e "  - Stop stack:    ${CYAN}ejiroinspire stop${NC}"
echo ""
