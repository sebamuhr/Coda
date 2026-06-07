#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  Coda Installer
#  https://github.com/sebamuhr/Coda
# ═══════════════════════════════════════════════════════════════

set -e

OS=$(uname -s)   # Linux or Darwin

REPO="https://raw.githubusercontent.com/sebamuhr/Coda/main"
CODA_DIR="$HOME/Coda"
CONFIG_DIR="$HOME/.config/coda"

BOLD=$(tput bold 2>/dev/null || echo "")
RESET=$(tput sgr0 2>/dev/null || echo "")
GRAY='\033[0;90m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

step() { echo ""; echo -e "${BLUE}${BOLD}[$1/$STEPS]${RESET} $2"; }
ok()   { echo -e "    ${GREEN}✓  $1${NC}"; }
warn() { echo -e "    ${YELLOW}⚠  $1${NC}"; }
ask()  { echo -e "${YELLOW}$1${NC}"; }
hr()   { echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
lc()   { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

STEPS=8

# ── Banner ────────────────────────────────────────────────────
clear
echo ""
echo -e "${BLUE}${BOLD}"
cat << 'BANNER'
   ██████╗ ██████╗ ██████╗  █████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔══██╗
  ██║     ██║   ██║██║  ██║███████║
  ██║     ██║   ██║██║  ██║██╔══██║
  ╚██████╗╚██████╔╝██████╔╝██║  ██║
   ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝
BANNER
echo -e "${RESET}"
echo "  Your local AI assistant — code, email, no subscription"
echo "  https://github.com/sebamuhr/Coda"
echo ""
hr
echo ""

# ── AI Provider ───────────────────────────────────────────────
ask "Which AI provider do you want to use?"
echo ""
echo "  1) Ollama  (local)  — your own model, 100% private, no API key needed"
echo "  2) Gemini           — Google AI, free tier at aistudio.google.com"
echo "  3) Claude API       — Anthropic, best for complex code (paid)"
echo "  4) OpenAI           — GPT-4o and others (paid)"
echo ""
read -p "  Choice [1]: " PROVIDER_CHOICE
PROVIDER_CHOICE=${PROVIDER_CHOICE:-1}

OLLAMA_IP=""
MODEL=""
API_KEY=""

case "$PROVIDER_CHOICE" in
  1)
    PROVIDER="Ollama (local)"
    echo ""
    ask "Where is Ollama running?"
    echo "  Use 'localhost' if it's on this machine, or enter the server IP."
    echo ""
    read -p "  Ollama IP [localhost]: " OLLAMA_IP
    OLLAMA_IP=${OLLAMA_IP:-localhost}
    # Strip any http:// prefix the user might type
    OLLAMA_IP="${OLLAMA_IP#http://}"
    OLLAMA_IP="${OLLAMA_IP%%:*}"

    echo ""
    echo -e "  Testing connection to ${CYAN}http://${OLLAMA_IP}:11434${NC}..."
    if curl -s --connect-timeout 5 "http://${OLLAMA_IP}:11434" 2>/dev/null | grep -q "Ollama"; then
        ok "Connected!"
    else
        warn "Could not reach Ollama — check it is running and accessible."
        read -p "  Continue anyway? [y/N]: " CONT
        [ "$(lc "$CONT")" = "y" ] || exit 1
    fi

    echo ""
    ask "Which model do you want to use?"
    echo -e "  ${GRAY}(no GPU? qwen2.5:3b is a good choice)${NC}"
    MODELS_JSON=$(curl -s --connect-timeout 5 "http://${OLLAMA_IP}:11434/api/tags" 2>/dev/null) || true
    if [ -n "$MODELS_JSON" ]; then
        echo "  Models on your server:"
        echo "$MODELS_JSON" | python3 -c "
import json,sys
for m in json.load(sys.stdin).get('models',[]): print('    •', m['name'])
" 2>/dev/null || true
        echo ""
    fi
    read -p "  Model name: " MODEL
    [ -n "$MODEL" ] || { echo -e "${RED}Model name is required.${NC}"; exit 1; }
    ;;

  2)
    PROVIDER="Gemini"
    echo ""
    ask "Gemini API key  (get one free at aistudio.google.com):"
    read -p "  API key: " API_KEY
    [ -n "$API_KEY" ] || { echo -e "${RED}API key is required.${NC}"; exit 1; }
    echo ""
    ask "Which model?  (leave blank for gemini-2.0-flash)"
    echo "  Options: gemini-2.0-flash   gemini-1.5-pro   gemini-1.5-flash"
    read -p "  Model [gemini-2.0-flash]: " MODEL
    MODEL=${MODEL:-gemini-2.0-flash}
    ;;

  3)
    PROVIDER="Claude"
    echo ""
    ask "Anthropic API key  (console.anthropic.com):"
    read -p "  API key: " API_KEY
    [ -n "$API_KEY" ] || { echo -e "${RED}API key is required.${NC}"; exit 1; }
    echo ""
    ask "Which model?  (leave blank for claude-sonnet-4-5)"
    echo "  Options: claude-opus-4-5   claude-sonnet-4-5   claude-haiku-4-5"
    read -p "  Model [claude-sonnet-4-5]: " MODEL
    MODEL=${MODEL:-claude-sonnet-4-5}
    ;;

  4)
    PROVIDER="OpenAI"
    echo ""
    ask "OpenAI API key  (platform.openai.com):"
    read -p "  API key: " API_KEY
    [ -n "$API_KEY" ] || { echo -e "${RED}API key is required.${NC}"; exit 1; }
    echo ""
    ask "Which model?  (leave blank for gpt-4o)"
    echo "  Options: gpt-4o   gpt-4o-mini   gpt-4-turbo"
    read -p "  Model [gpt-4o]: " MODEL
    MODEL=${MODEL:-gpt-4o}
    ;;

  *)
    echo -e "${RED}Invalid choice.${NC}"; exit 1
    ;;
esac

# ── Your name ──────────────────────────────────────────────────
echo ""
ask "Your first name  (used for email sign-offs):"
read -p "  Name: " USER_NAME
USER_NAME=${USER_NAME:-User}

# ── Terminal alias ─────────────────────────────────────────────
ALIAS_NAME="coda"
echo ""
ask "Terminal command:"
echo -e "  ${GRAY}coda${NC}"

# ── Email Agent ────────────────────────────────────────────────
echo ""
hr
echo ""
ask "Email Agent setup  (reads inbox, writes replies with AI)"
echo -e "  ${GRAY}This needs a Gmail App Password — myaccount.google.com/apppasswords${NC}"
echo ""
read -p "  Set up Email Agent now? [y/N]: " SETUP_EMAIL

EMAIL_ADDR=""
APP_PASSWORD=""
EMAIL_PROVIDER="Gmail"
IMAP_SERVER="imap.gmail.com"
SMTP_SERVER="smtp.gmail.com"

if [ "$(lc "$SETUP_EMAIL")" = "y" ]; then
    echo ""
    ask "Email address:"
    read -p "  Email: " EMAIL_ADDR
    echo ""
    ask "App Password:"
    echo -e "  ${GRAY}16 characters — get it at myaccount.google.com/apppasswords${NC}"
    echo -e "  ${GRAY}(requires 2-Step Verification to be enabled on your Google account)${NC}"
    read -p "  App Password: " APP_PASSWORD
    echo ""
fi

# ── Confirm ────────────────────────────────────────────────────
echo ""
hr
echo -e "  ${BOLD}Ready to install with:${RESET}"
echo ""
echo "    Provider  :  $PROVIDER"
[ -n "$OLLAMA_IP" ] && echo "    Ollama    :  http://${OLLAMA_IP}:11434"
echo "    Model     :  $MODEL"
echo "    Command   :  $ALIAS_NAME"
echo "    Your name :  $USER_NAME"
[ -n "$EMAIL_ADDR" ] && echo "    Email     :  $EMAIL_ADDR"
echo ""
hr
echo ""
read -p "  Proceed? [Y/n]: " PROCEED
[ "$(lc "$PROCEED")" = "n" ] && { echo "Aborted."; exit 0; }
echo ""

# ══════════════════════════════════════════════════════════════
#  INSTALLATION
# ══════════════════════════════════════════════════════════════

# ── 1: System packages ─────────────────────────────────────────
step 1 "Installing system packages..."
if [ "$OS" = "Darwin" ]; then
    if ! command -v brew &>/dev/null; then
        warn "Homebrew not found — install it from brew.sh, then re-run this installer."
        exit 1
    fi
    brew install python-tk 2>/dev/null || true
else
    sudo apt-get install -y -q \
        python3 python3-pip python3-tk python3-venv \
        python3-nautilus gir1.2-ayatanaappindicator3-0.1 \
        wmctrl libnotify-bin 2>/dev/null || true
fi
ok "Done"

# ── 2: Python packages ─────────────────────────────────────────
step 2 "Installing Python packages..."
python3 -m pip install pystray pillow --break-system-packages -q 2>/dev/null \
    || python3 -m pip install pystray pillow --user -q
ok "pystray and pillow installed"

# ── 3: Aider ───────────────────────────────────────────────────
step 3 "Setting up Aider  (the coding engine)..."
echo -e "  ${GRAY}This may take a few minutes…${NC}"
if [ ! -d "$HOME/aider-env" ]; then
    python3 -m venv ~/aider-env
fi
source ~/aider-env/bin/activate
pip install aider-chat
deactivate
ok "Aider installed in ~/aider-env"

# ── 4: Download Coda ───────────────────────────────────────────
step 4 "Downloading Coda..."
mkdir -p "$CODA_DIR"
for f in coda-tray.py coda-email.py coda-preferences.py; do
    echo -e "    Downloading ${CYAN}${f}${NC}..."
    curl -fsSL "${REPO}/${f}" -o "${CODA_DIR}/${f}"
done
ok "All files saved to ~/Coda/"

# ── 5: Email AI model (coda2.0:3b) ────────────────────────────
step 5 "Setting up Email AI (coda2.0:3b)..."
echo ""
echo -e "  ${CYAN}The Email Assistant uses a dedicated local model (coda2.0:3b).${NC}"
echo "  This is completely separate from your Call Coda setup."
echo "  You need Ollama running — get it free at ollama.com"
echo ""
ask "Where is Ollama running for the Email Assistant?"
echo -e "  ${GRAY}Enter 'localhost' if Ollama is on this machine, or an IP like 192.168.1.50${NC}"
read -p "  Ollama IP [localhost]: " EMAIL_OLLAMA_IP
EMAIL_OLLAMA_IP=${EMAIL_OLLAMA_IP:-localhost}
EMAIL_OLLAMA_IP="${EMAIL_OLLAMA_IP#http://}"
EMAIL_OLLAMA_IP="${EMAIL_OLLAMA_IP%%:*}"
EMAIL_OLLAMA_URL="http://${EMAIL_OLLAMA_IP}:11434"

EMAIL_MODEL_READY=false

while true; do
    echo ""
    echo -e "  Testing connection to ${CYAN}${EMAIL_OLLAMA_URL}${NC}..."
    if curl -s --connect-timeout 5 "${EMAIL_OLLAMA_URL}" 2>/dev/null | grep -q "Ollama"; then
        ok "Connected to Ollama!"
        EMAIL_MODEL_READY=true
        break
    else
        echo -e "  ${RED}Cannot reach Ollama at ${EMAIL_OLLAMA_URL}${NC}"
        echo ""
        echo "  What would you like to do?"
        echo "    1) Try a different IP"
        echo "    2) Retry same address"
        if [ "$OS" = "Darwin" ]; then
            echo "    3) Install Ollama  (download from ollama.com and run the macOS app)"
        else
            echo "    3) Install Ollama on this machine  (free, runs locally)"
        fi
        echo "    4) Skip — set up later from Preferences → Email → Pull Model"
        echo ""
        read -p "  Choice [1]: " RETRY_CHOICE
        RETRY_CHOICE=${RETRY_CHOICE:-1}
        case "$RETRY_CHOICE" in
            1)
                read -p "  Ollama IP: " EMAIL_OLLAMA_IP
                EMAIL_OLLAMA_IP="${EMAIL_OLLAMA_IP#http://}"
                EMAIL_OLLAMA_IP="${EMAIL_OLLAMA_IP%%:*}"
                EMAIL_OLLAMA_URL="http://${EMAIL_OLLAMA_IP}:11434"
                ;;
            2) ;;
            3)
                if [ "$OS" = "Darwin" ]; then
                    warn "Download and install Ollama from ollama.com, then re-run this installer."
                    EMAIL_OLLAMA_IP="localhost"
                    break
                fi
                echo ""
                echo "  Installing Ollama..."
                curl -fsSL https://ollama.com/install.sh | sh
                echo ""
                echo "  Waiting for Ollama to start..."
                sleep 4
                EMAIL_OLLAMA_IP="localhost"
                EMAIL_OLLAMA_URL="http://localhost:11434"
                ;;
            4)
                warn "Email model skipped — use Preferences → Email → Pull Model to install later."
                EMAIL_OLLAMA_IP="localhost"
                break
                ;;
        esac
    fi
done

if [ "$EMAIL_MODEL_READY" = "true" ]; then
    echo ""
    echo "    Downloading qwen2.5:3b (this may take several minutes)..."
    EMAIL_OLLAMA_URL="$EMAIL_OLLAMA_URL" python3 << 'PYEOF'
import urllib.request, json, os, sys

url = os.environ['EMAIL_OLLAMA_URL']

# Pull qwen2.5:3b — streaming so the connection stays alive
data = json.dumps({'model': 'qwen2.5:3b', 'stream': True}).encode()
req  = urllib.request.Request(f'{url}/api/pull', data=data,
                               headers={'Content-Type': 'application/json'})
try:
    last_pct = -1
    with urllib.request.urlopen(req, timeout=60) as resp:
        while True:
            line = resp.readline()
            if not line:
                break
            try:
                obj   = json.loads(line)
                total = obj.get('total', 0)
                done  = obj.get('completed', 0)
                if total and done:
                    pct = int(done / total * 100)
                    if pct != last_pct:
                        print(f'\r    Downloading qwen2.5:3b… {pct}%', end='', flush=True)
                        last_pct = pct
            except Exception:
                pass
    print()
except Exception as e:
    print(f'\n    Error during download: {e}', file=sys.stderr)
    sys.exit(1)

# Create coda2.0:3b using current Ollama API (from + system fields)
print('    Creating coda2.0:3b…')
data = json.dumps({
    'model': 'coda2.0:3b',
    'from': 'qwen2.5:3b',
    'system': ('You write emails on behalf of the user. '
               'Write naturally and concisely in their voice. '
               'Do not use robotic phrases or unnecessary pleasantries.'),
    'stream': True
}).encode()
req  = urllib.request.Request(f'{url}/api/create', data=data,
                               headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        while resp.readline():
            pass
except Exception as e:
    print(f'    Warning during create: {e}', file=sys.stderr)

# Remove qwen2.5:3b
print('    Removing qwen2.5:3b…')
data = json.dumps({'name': 'qwen2.5:3b'}).encode()
req  = urllib.request.Request(f'{url}/api/delete', data=data,
                               headers={'Content-Type': 'application/json'},
                               method='DELETE')
try:
    urllib.request.urlopen(req, timeout=30)
except Exception:
    pass

# Verify coda2.0:3b is there
with urllib.request.urlopen(f'{url}/api/tags', timeout=5) as r:
    models = [m['name'] for m in json.loads(r.read()).get('models', [])]
if any('coda2.0:3b' in m for m in models):
    print('    Verified: coda2.0:3b is installed')
else:
    print('    ERROR: coda2.0:3b not found after setup', file=sys.stderr)
    sys.exit(1)
PYEOF

    if [ $? -eq 0 ]; then
        ok "coda2.0:3b ready!"
    else
        warn "Model setup had issues — use Preferences → Email → Pull Model to retry."
        EMAIL_MODEL_READY=false
    fi
fi

# ── 6: Configuration ───────────────────────────────────────────
step 6 "Writing configuration..."
mkdir -p "$CONFIG_DIR"

# Write config.json via Python (handles special characters in API keys safely)
PROVIDER="$PROVIDER" OLLAMA_IP="$OLLAMA_IP" MODEL="$MODEL" \
API_KEY="$API_KEY" EMAIL_PROVIDER="$EMAIL_PROVIDER" \
EMAIL_ADDR="$EMAIL_ADDR" APP_PASSWORD="$APP_PASSWORD" \
IMAP_SERVER="$IMAP_SERVER" SMTP_SERVER="$SMTP_SERVER" \
ALIAS_NAME="$ALIAS_NAME" USER_NAME="$USER_NAME" \
EMAIL_OLLAMA_IP="$EMAIL_OLLAMA_IP" \
python3 << 'PYEOF'
import json, os
cfg = {
    "provider":         os.environ["PROVIDER"],
    "ollama_ip":        os.environ["OLLAMA_IP"],
    "model":            os.environ["MODEL"],
    "api_key":          os.environ["API_KEY"],
    "custom_url":       "",
    "email_provider":   os.environ["EMAIL_PROVIDER"],
    "email":            os.environ["EMAIL_ADDR"],
    "app_password":     os.environ["APP_PASSWORD"],
    "imap_server":      os.environ["IMAP_SERVER"],
    "smtp_server":      os.environ["SMTP_SERVER"],
    "alias":            os.environ["ALIAS_NAME"],
    "refresh_minutes":  5,
    "user_name":        os.environ["USER_NAME"],
    "email_ollama_ip":  os.environ["EMAIL_OLLAMA_IP"],
}
path = os.path.expanduser("~/.config/coda/config.json")
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
os.chmod(path, 0o600)
PYEOF

# Write email.conf (used by the email agent)
EMAIL_ADDR="$EMAIL_ADDR" APP_PASSWORD="$APP_PASSWORD" \
IMAP_SERVER="$IMAP_SERVER" SMTP_SERVER="$SMTP_SERVER" \
EMAIL_PROVIDER="$EMAIL_PROVIDER" EMAIL_OLLAMA_IP="$EMAIL_OLLAMA_IP" \
python3 << 'PYEOF'
import os
lines = [
    f"EMAIL={os.environ['EMAIL_ADDR']}",
    f"APP_PASSWORD={os.environ['APP_PASSWORD']}",
    f"IMAP_SERVER={os.environ['IMAP_SERVER']}",
    f"SMTP_SERVER={os.environ['SMTP_SERVER']}",
    f"PROVIDER={os.environ['EMAIL_PROVIDER']}",
    f"EMAIL_OLLAMA_IP={os.environ['EMAIL_OLLAMA_IP']}",
]
path = os.path.expanduser("~/.config/coda/email.conf")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    f.write("\n".join(lines) + "\n")
os.chmod(path, 0o600)
PYEOF

ok "Configuration saved to ~/.config/coda/"

# ── 7: Terminal alias ──────────────────────────────────────────
step 7 "Setting up '${ALIAS_NAME}' terminal command..."

if [ "$OS" = "Darwin" ]; then
    RC_FILE="$HOME/.zshrc"
    sed -i '' '/# Coda - Local AI/d' "$RC_FILE" 2>/dev/null || true
    sed -i '' '/alias coda/d'        "$RC_FILE" 2>/dev/null || true
else
    RC_FILE="$HOME/.bashrc"
    sed -i '/# Coda - Local AI/d' "$RC_FILE" 2>/dev/null || true
    sed -i '/alias coda/d'        "$RC_FILE" 2>/dev/null || true
fi

if [ "$PROVIDER" = "Ollama (local)" ]; then
    ALIAS_CMD="source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://${OLLAMA_IP}:11434 aider --model ollama/${MODEL}"
elif [ "$PROVIDER" = "Gemini" ]; then
    ALIAS_CMD="source ~/aider-env/bin/activate && GEMINI_API_KEY=${API_KEY} aider --model gemini/${MODEL}"
elif [ "$PROVIDER" = "Claude" ]; then
    ALIAS_CMD="source ~/aider-env/bin/activate && ANTHROPIC_API_KEY=${API_KEY} aider --model ${MODEL}"
elif [ "$PROVIDER" = "OpenAI" ]; then
    ALIAS_CMD="source ~/aider-env/bin/activate && OPENAI_API_KEY=${API_KEY} aider --model ${MODEL}"
fi

{
    echo ""
    echo "# Coda - Local AI coding assistant"
    printf "alias %s='%s'\n" "$ALIAS_NAME" "$ALIAS_CMD"
} >> "$RC_FILE"

if [ "$OS" = "Darwin" ]; then
    ok "'${ALIAS_NAME}' command ready  (run: source ~/.zshrc)"
else
    ok "'${ALIAS_NAME}' command ready  (run: source ~/.bashrc)"
fi

# ── 8: Desktop integration ─────────────────────────────────────
step 8 "Setting up desktop integration..."

if [ "$OS" = "Darwin" ]; then
    PLIST_DIR="$HOME/Library/LaunchAgents"
    mkdir -p "$PLIST_DIR"
    PYTHON_BIN=$(which python3)
    cat > "$PLIST_DIR/com.coda.plist" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.coda.tray</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${CODA_DIR}/coda-tray.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
PLISTEOF
    launchctl load "$PLIST_DIR/com.coda.plist" 2>/dev/null || true
    ok "LaunchAgent installed — Coda will start on login"
else
    # Nautilus right-click extension
    mkdir -p "$HOME/.local/share/nautilus-python/extensions/"
    curl -fsSL "${REPO}/coda_extension.py" \
         -o "$HOME/.local/share/nautilus-python/extensions/coda_extension.py" -q
    nautilus -q 2>/dev/null || true
    ok "Right-click 'Call Coda' installed"

    # Icon
    mkdir -p ~/.local/share/icons
    cat > ~/.local/share/icons/coda.svg << 'SVGEOF'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="20" fill="#ffffff" stroke="#000000" stroke-width="4"/>
  <text x="50" y="72" font-family="DejaVu Sans,sans-serif" font-size="72"
        font-weight="bold" fill="#000000" text-anchor="middle">C</text>
</svg>
SVGEOF

    # App launcher entry
    mkdir -p ~/.local/share/applications
    cat > ~/.local/share/applications/coda.desktop << DESKEOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Coda
Comment=Your local AI assistant
Exec=/usr/bin/python3 ${CODA_DIR}/coda-tray.py
Icon=${HOME}/.local/share/icons/coda.svg
Terminal=false
Categories=Development;Utility;
StartupNotify=false
DESKEOF
    chmod +x ~/.local/share/applications/coda.desktop
    [ -d ~/Desktop ] && cp ~/.local/share/applications/coda.desktop ~/Desktop/ \
        && chmod +x ~/Desktop/coda.desktop

    # Autostart on login
    mkdir -p ~/.config/autostart
    cat > ~/.config/autostart/coda.desktop << AUTOEOF
[Desktop Entry]
Type=Application
Name=Coda
Exec=/usr/bin/python3 ${CODA_DIR}/coda-tray.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
AUTOEOF

    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
    ok "App launcher entry, desktop icon and autostart on login ready"
fi

# ══════════════════════════════════════════════════════════════
#  DONE
# ══════════════════════════════════════════════════════════════
echo ""
hr
echo -e "  ${GREEN}${BOLD}✓  Coda installed!${RESET}"
hr
echo ""
echo "  How to use:"
echo ""
if [ "$OS" = "Darwin" ]; then
    echo -e "  ${CYAN}System tray:${NC}"
    echo "    Coda starts automatically on login."
    echo "    The C icon appears in your menu bar — click it to code or check email."
    echo ""
    echo -e "  ${CYAN}Terminal:${NC}"
    echo "    source ~/.zshrc"
    echo "    cd ~/my-project && ${ALIAS_NAME}"
else
    echo -e "  ${CYAN}System tray:${NC}"
    echo "    Search 'Coda' in your app launcher and click it."
    echo "    The C icon appears in your taskbar — click it to code or check email."
    echo ""
    echo -e "  ${CYAN}Right-click any project folder:${NC}"
    echo "    Open file manager → right-click a folder → Call Coda"
    echo ""
    echo -e "  ${CYAN}Terminal:${NC}"
    echo "    source ~/.bashrc"
    echo "    cd ~/my-project && ${ALIAS_NAME}"
fi
echo ""
echo -e "  ${CYAN}Change settings anytime:${NC}"
echo "    C icon in taskbar → Preferences"
echo ""
hr
echo ""
read -p "  Start Coda now? [Y/n]: " START_NOW
if [ "$(lc "$START_NOW")" != "n" ]; then
    python3 "${CODA_DIR}/coda-tray.py" &
    echo ""
    ok "Coda is running — look for the C icon in your menu bar!"
fi
echo ""
