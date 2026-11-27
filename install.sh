#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Coda installer — https://github.com/sebamuhr/Coda
#
#    bash <(curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/install.sh)
#
#  Safe to run again: it updates the existing install in place, keeps your
#  settings, and removes old duplicate copies and launchers.
#
#  Options:
#    --yes            no questions; use defaults (configure later in Preferences)
#    --reconfigure    ask the setup questions even if Coda is already configured
#    --skip-system    don't install system packages (apt / brew)
#    --engine NAME    coding agent "Call Coda" opens: claude, codex, cursor-agent,
#                     gemini or aider (default: the first one already installed,
#                     else aider)
#    --skip-aider     don't install aider
#    --no-autostart   don't start Coda on login
#    --no-start       don't start Coda when the install finishes
#
#  Everything goes in:
#    ~/.local/share/coda    app, Python environments
#    ~/.config/coda         your settings and contacts
#    ~/.local/bin/coda      the 'coda' command
#  Remove it all with:  coda uninstall
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

REPO="sebamuhr/Coda"
BRANCH="${CODA_BRANCH:-main}"
OS=$(uname -s)
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/coda"
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/coda/config.json"

YES=0; RECONFIGURE=0; SKIP_SYSTEM=0; SKIP_AIDER=0; AUTOSTART=1; START=1; ENGINE=""
while [ $# -gt 0 ]; do
    arg=$1; shift
    case "$arg" in
        --engine)        ENGINE=${1:-}; shift || true ;;
        --engine=*)      ENGINE=${arg#--engine=} ;;
        --yes|-y)        YES=1 ;;
        --reconfigure)   RECONFIGURE=1 ;;
        --skip-system)   SKIP_SYSTEM=1 ;;
        --skip-aider)    SKIP_AIDER=1 ;;
        --no-autostart)  AUTOSTART=0 ;;
        --no-start)      START=0 ;;
        -h|--help)       sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg (see --help)"; exit 1 ;;
    esac
done
case "$ENGINE" in ""|claude|codex|cursor-agent|gemini|aider) ;;
    *) echo "Unknown --engine '$ENGINE' (claude, codex, cursor-agent, gemini, aider)"; exit 1 ;;
esac

BOLD=$(tput bold 2>/dev/null || true); RESET=$(tput sgr0 2>/dev/null || true)
GRAY='\033[0;90m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
STEPS=7
step() { echo; echo -e "${BLUE}${BOLD}[$1/$STEPS]${RESET} $2"; }
ok()   { echo -e "    ${GREEN}✓  $1${NC}"; }
warn() { echo -e "    ${YELLOW}⚠  $1${NC}"; }
die()  { echo -e "${RED}✗  $1${NC}" >&2; exit 1; }
lc()   { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
ask()  {  # ask VAR "question" "default" [secret]
    local __var=$1 __q=$2 __def=${3:-} __ans=""
    if [ "$YES" = 1 ]; then printf -v "$__var" '%s' "$__def"; return; fi
    if [ "${4:-}" = secret ]; then read -r -s -p "  $__q: " __ans; echo
    else read -r -p "  $__q${__def:+ [$__def]}: " __ans; fi
    printf -v "$__var" '%s' "${__ans:-$__def}"
}
yesno() { local a; ask a "$1 [y/N]" "${2:-n}"; [ "$(lc "$a")" = y ] || [ "$(lc "$a")" = yes ]; }

echo -e "${BLUE}${BOLD}"
cat << 'BANNER'
   ██████╗ ██████╗ ██████╗  █████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔══██╗
  ██║     ██║   ██║██║  ██║███████║
  ██║     ██║   ██║██║  ██║██╔══██║
  ╚██████╗╚██████╔╝██████╔╝██║  ██║
   ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝
BANNER
echo -e "${RESET}  Your local AI assistant — code and email, no subscription"
echo

command -v python3 >/dev/null || die "python3 is required."
command -v curl    >/dev/null || die "curl is required."

# Stop any running Coda (from any location) so files can be replaced safely.
if pgrep -f 'coda-(tray|email|preferences)\.py' >/dev/null 2>&1; then
    pkill -f 'coda-(tray|email|preferences)\.py' || true
    sleep 1
    echo -e "  ${GRAY}Stopped the running Coda — it restarts at the end.${NC}"
fi

# ── 1: System packages ──────────────────────────────────────────
step 1 "System packages"
if [ "$SKIP_SYSTEM" = 1 ]; then
    ok "skipped"
elif [ "$OS" = Darwin ]; then
    command -v brew >/dev/null || die "Homebrew is required on macOS — install it from https://brew.sh"
    brew install python-tk >/dev/null 2>&1 || warn "could not install python-tk"
    ok "python-tk"
elif command -v apt-get >/dev/null; then
    echo -e "  ${GRAY}Needs your password for apt-get.${NC}"
    sudo apt-get install -y -q python3-venv python3-tk python3-gi python3-nautilus \
        gir1.2-ayatanaappindicator3-0.1 libnotify-bin >/dev/null \
        || warn "some packages failed to install — Coda may still work"
    ok "python3-venv, tk, nautilus-python, app indicator"
else
    warn "Not a Debian/Ubuntu system — install the equivalents of: python3-venv python3-tk"
    warn "python3-gi, nautilus-python and an AppIndicator library, then re-run with --skip-system."
fi

# ── 2: Coda itself ──────────────────────────────────────────────
step 2 "Coda app"
SRC_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/coda.py" ]; then
    SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
fi
mkdir -p "$DATA_DIR"
if [ -n "$SRC_DIR" ] && [ -d "$SRC_DIR/.git" ]; then
    # Developer checkout: run straight from it so edits take effect immediately.
    CODE_DIR="$SRC_DIR"
    ok "using your git checkout at $CODE_DIR"
else
    CODE_DIR="$DATA_DIR/app"
    TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
    if [ -n "$SRC_DIR" ]; then
        mkdir -p "$TMP/coda" && cp -a "$SRC_DIR/." "$TMP/coda/"
    else
        curl -fsSL "https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP"
        mv "$TMP"/Coda-* "$TMP/coda"
    fi
    [ -f "$TMP/coda/coda.py" ] || die "download does not look like Coda"
    rm -rf "$CODE_DIR.old"; [ -d "$CODE_DIR" ] && mv "$CODE_DIR" "$CODE_DIR.old"
    mv "$TMP/coda" "$CODE_DIR"; rm -rf "$CODE_DIR.old"
    ok "installed to $CODE_DIR"
fi

# ── 3: Python environment for the tray ──────────────────────────
step 3 "Python environment"
VENV="$DATA_DIR/venv"
# --system-site-packages: the tray needs the system's GTK/AppIndicator bindings.
[ -x "$VENV/bin/python3" ] || python3 -m venv --system-site-packages "$VENV" \
    || die "could not create a Python venv (on Ubuntu: sudo apt install python3-venv)"
"$VENV/bin/python3" -m pip install -q --upgrade pip
"$VENV/bin/python3" -m pip install -q pystray pillow requests anthropic
PY="$VENV/bin/python3"
ok "$VENV"

# ── 4: Coding agent ─────────────────────────────────────────────
step 4 "Coding agent for right-click → Call Coda"
if [ -z "$ENGINE" ] && [ -f "$CONFIG_FILE" ] && [ "$RECONFIGURE" = 0 ]; then
    ENGINE=$("$PY" -c "import sys; sys.path.insert(0,'$CODE_DIR'); import coda_common as C; print(C.load_config().get('engine','aider'))")
fi
if [ -z "$ENGINE" ]; then
    FOUND=$("$PY" -c "import sys; sys.path.insert(0,'$CODE_DIR'); import coda_common as C; print(' '.join(e for e in C.installed_engines() if e != 'aider'))")
    DEFAULT_ENGINE=${FOUND%% *}; DEFAULT_ENGINE=${DEFAULT_ENGINE:-aider}
    [ -n "$FOUND" ] && echo -e "  ${GRAY}Found on this computer: ${FOUND}${NC}"
    echo "    claude        Claude Code"
    echo "    codex         Codex CLI"
    echo "    cursor-agent  Cursor Agent"
    echo "    gemini        Gemini CLI"
    echo "    aider         Aider — works with local Ollama models, Gemini, Claude or OpenAI keys"
    ask ENGINE "Which agent should open" "$DEFAULT_ENGINE"
fi
"$PY" -c "import sys; sys.path.insert(0,'$CODE_DIR'); import coda_common as C; sys.exit(0 if C.find_engine('$ENGINE') or '$ENGINE'=='aider' else 1)" \
    || warn "$ENGINE is not installed yet — install it, or pick another agent later in Preferences"
ok "Call Coda opens: $ENGINE"
[ "$ENGINE" = aider ] || SKIP_AIDER=1
EXISTING_AIDER=""
for a in "$DATA_DIR/aider-env/bin/aider" "$HOME/aider-env/bin/aider" "$(command -v aider || true)"; do
    [ -n "$a" ] && [ -x "$a" ] && { EXISTING_AIDER="$a"; break; }
done
if [ "$SKIP_AIDER" = 1 ]; then
    if [ "$ENGINE" = aider ]; then ok "aider: skipped"; fi
elif [ -n "$EXISTING_AIDER" ]; then
    ok "already installed: $EXISTING_AIDER"
else
    # aider-chat supports Python 3.10–3.12.
    VPY=""
    for p in python3.12 python3.11 python3.10; do command -v "$p" >/dev/null && { VPY=$p; break; }; done
    if [ -z "$VPY" ] && [ "$OS" = Darwin ]; then
        brew install -q python@3.12 && VPY="$(brew --prefix python@3.12)/bin/python3.12"
    fi
    [ -n "$VPY" ] || die "aider needs Python 3.10–3.12; install one, or re-run with --skip-aider"
    echo -e "  ${GRAY}This takes a few minutes…${NC}"
    "$VPY" -m venv "$DATA_DIR/aider-env"
    "$DATA_DIR/aider-env/bin/pip" install -q --upgrade pip
    "$DATA_DIR/aider-env/bin/pip" install -q --prefer-binary aider-chat
    ok "$DATA_DIR/aider-env"
fi

# ── 5: Settings ─────────────────────────────────────────────────
step 5 "Settings"
if [ -f "$CONFIG_FILE" ] && [ "$RECONFIGURE" = 0 ]; then
    ok "keeping your existing settings (re-run with --reconfigure to change them)"
    CODE_DIR="$CODE_DIR" ENGINE="$ENGINE" "$PY" -c "import os,sys; sys.path.insert(0,os.environ['CODE_DIR']); import coda_common as C; c=C.load_config(); c['engine']=os.environ['ENGINE']; C.save_config(c)"
    EMAIL_OLLAMA_IP=$("$PY" -c "import sys; sys.path.insert(0,'$CODE_DIR'); import coda_common as C; print(C.load_config()['email_ollama_ip'])")
else
  OLLAMA_IP=localhost; MODEL=""; API_KEY=""; PROVIDER="Ollama (local)"
  if [ "$ENGINE" = aider ]; then
    echo "  Which AI should aider use?"
    echo "    1) Ollama  — local, private, free"
    echo "    2) Gemini  — Google, has a free tier"
    echo "    3) Claude  — Anthropic"
    echo "    4) OpenAI"
    ask CHOICE "Choice" 1
    case "$CHOICE" in
        1) PROVIDER="Ollama (local)"
           ask OLLAMA_IP "Ollama server (localhost or an IP)" localhost
           if curl -s --connect-timeout 4 "http://${OLLAMA_IP}:11434/api/tags" >/dev/null; then
               echo -e "  ${GRAY}Models on that server:${NC}"
               curl -s "http://${OLLAMA_IP}:11434/api/tags" | "$PY" -c \
                   "import json,sys; [print('    •', m['name']) for m in json.load(sys.stdin).get('models',[])]" || true
           else
               warn "Ollama not reachable at ${OLLAMA_IP}:11434 — you can fix this later in Preferences"
           fi
           ask MODEL "Model" "qwen2.5-coder:7b" ;;
        2) PROVIDER="Gemini"; ask API_KEY "Gemini API key (aistudio.google.com)" "" secret
           ask MODEL "Model" "gemini-2.5-flash" ;;
        3) PROVIDER="Claude"; ask API_KEY "Anthropic API key (console.anthropic.com)" "" secret
           ask MODEL "Model" "claude-sonnet-5-5" ;;
        4) PROVIDER="OpenAI"; ask API_KEY "OpenAI API key (platform.openai.com)" "" secret
           ask MODEL "Model" "gpt-4o" ;;
        *) die "Invalid choice" ;;
    esac
  else
    ask OLLAMA_IP "Ollama server for the Email Agent (localhost or an IP)" localhost
  fi
    ask USER_NAME "Your first name (for email sign-offs)" ""
    EMAIL_ADDR=""; APP_PASSWORD=""
    if yesno "Set up the Email Agent now? (needs an app password)"; then
        ask EMAIL_ADDR "Email address" ""
        ask APP_PASSWORD "App password (Gmail: myaccount.google.com/apppasswords)" "" secret
    fi
    ask EMAIL_OLLAMA_IP "Ollama server for the Email Agent (always local AI)" "$OLLAMA_IP"
    ENGINE="$ENGINE" PROVIDER="$PROVIDER" OLLAMA_IP="$OLLAMA_IP" MODEL="$MODEL" API_KEY="$API_KEY" \
    USER_NAME="$USER_NAME" EMAIL_ADDR="$EMAIL_ADDR" APP_PASSWORD="$APP_PASSWORD" \
    EMAIL_OLLAMA_IP="$EMAIL_OLLAMA_IP" CODE_DIR="$CODE_DIR" "$PY" - << 'PYEOF'
import os, sys
sys.path.insert(0, os.environ['CODE_DIR'])
import coda_common as C
e = os.environ
cfg = C.load_config()
cfg.update(engine=e['ENGINE'], provider=e['PROVIDER'], ollama_ip=e['OLLAMA_IP'], model=e['MODEL'],
           email_ollama_ip=e['EMAIL_OLLAMA_IP'])
# Blank answers never wipe a value that is already there (e.g. from an older version).
for key, var in (('api_key', 'API_KEY'), ('user_name', 'USER_NAME'),
                 ('email', 'EMAIL_ADDR'), ('app_password', 'APP_PASSWORD')):
    if e[var]:
        cfg[key] = e[var]
C.save_config(cfg)
PYEOF
    ok "saved to $CONFIG_FILE (readable only by you)"
fi

# ── 6: Email AI model ───────────────────────────────────────────
step 6 "Email AI model (coda2.0:3b, ~2 GB)"
if [ "$YES" = 1 ]; then
    ok "skipped (--yes) — run 'coda email-model' or Preferences → Email → Pull Model"
elif curl -s --connect-timeout 4 "http://${EMAIL_OLLAMA_IP}:11434/api/tags" >/dev/null; then
    if yesno "Download it to ${EMAIL_OLLAMA_IP} now?" y; then
        "$PY" "$CODE_DIR/coda.py" email-model --host "$EMAIL_OLLAMA_IP" \
            || warn "failed — retry later from Preferences → Email → Pull Model"
    else
        ok "skipped — Preferences → Email → Pull Model"
    fi
else
    warn "Ollama not reachable at ${EMAIL_OLLAMA_IP}:11434 — skipped"
    if [ "$OS" = Darwin ]; then echo -e "  ${GRAY}Install it with: brew install ollama && brew services start ollama${NC}"
    else echo -e "  ${GRAY}Install it from https://ollama.com, then Preferences → Email → Pull Model${NC}"; fi
fi

# ── 7: Desktop integration (also removes old duplicates) ───────
step 7 "Launcher, autostart and right-click menu"
INTEGRATE_ARGS=()
[ "$YES" = 1 ] && INTEGRATE_ARGS+=(--yes)
[ "$AUTOSTART" = 0 ] && INTEGRATE_ARGS+=(--no-autostart)
"$PY" "$CODE_DIR/coda.py" integrate "${INTEGRATE_ARGS[@]}"

echo
echo -e "  ${GREEN}${BOLD}✓  Coda $("$PY" "$CODE_DIR/coda.py" version | cut -d' ' -f2) is installed.${RESET}"
echo
echo "    Tray icon      search 'Coda' in your apps (starts on login)"
[ "$OS" = Linux ] && echo "    Right-click    any folder in Files → Call Coda"
echo "    Terminal       cd my-project && coda"
echo "    Health check   coda doctor"
echo "    Uninstall      coda uninstall   (or Preferences → General)"
echo
if [ "$START" = 1 ]; then
    "$PY" "$CODE_DIR/coda.py" tray
    ok "Coda is running — look for the C icon"
fi
