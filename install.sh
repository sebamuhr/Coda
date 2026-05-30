#!/bin/bash

# ============================================================
#  Coda Installer
#  Local AI coding assistant for Linux
#  https://github.com/sebamuhr/Coda
# ============================================================

set -e

BOLD=$(tput bold)
RESET=$(tput sgr0)
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}${BOLD}"
echo "   ██████╗ ██████╗ ██████╗  █████╗ "
echo "  ██╔════╝██╔═══██╗██╔══██╗██╔══██╗"
echo "  ██║     ██║   ██║██║  ██║███████║"
echo "  ██║     ██║   ██║██║  ██║██╔══██║"
echo "  ╚██████╗╚██████╔╝██████╔╝██║  ██║"
echo "   ╚═════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝"
echo -e "${RESET}"
echo "  Your local AI coding assistant"
echo "  https://github.com/sebamuhr/Coda"
echo ""
echo "============================================================"
echo ""

# --- Ask for Ollama IP ---
echo -e "${YELLOW}Where is your Ollama server running?${NC}"
echo "  Examples: localhost  /  192.168.1.100  /  192.168.2.200"
echo ""
read -p "  Ollama IP or hostname: " OLLAMA_IP

if [ -z "$OLLAMA_IP" ]; then
    OLLAMA_IP="localhost"
fi

# --- Test Ollama connection ---
echo ""
echo -e "  Testing connection to Ollama at ${BLUE}http://${OLLAMA_IP}:11434${NC}..."
if curl -s --connect-timeout 5 "http://${OLLAMA_IP}:11434" | grep -q "Ollama"; then
    echo -e "  ${GREEN}✓ Ollama is reachable!${NC}"
else
    echo -e "  ${RED}✗ Could not reach Ollama at http://${OLLAMA_IP}:11434${NC}"
    echo "    Make sure Ollama is running and accessible."
    echo "    You can still continue but Coda won't work until Ollama is reachable."
    read -p "  Continue anyway? (y/n): " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 1
    fi
fi

# --- Ask for model name ---
echo ""
echo -e "${YELLOW}What model do you want to use?${NC}"
echo "  Examples: qwen2.5-coder:32b  /  qwen3.6:27b  /  coda:2.0"
echo ""

# Try to list available models
if curl -s --connect-timeout 5 "http://${OLLAMA_IP}:11434/api/tags" > /tmp/ollama_models.json 2>/dev/null; then
    echo "  Available models on your server:"
    python3 -c "
import json
with open('/tmp/ollama_models.json') as f:
    data = json.load(f)
for m in data.get('models', []):
    print('    -', m['name'])
" 2>/dev/null || true
    echo ""
fi

read -p "  Model name: " MODEL_NAME

if [ -z "$MODEL_NAME" ]; then
    echo -e "  ${RED}Model name cannot be empty.${NC}"
    exit 1
fi

# --- Ask for alias name ---
echo ""
echo -e "${YELLOW}What command do you want to type to launch Coda?${NC}"
echo "  Default: coda"
echo ""
read -p "  Command name [coda]: " ALIAS_NAME

if [ -z "$ALIAS_NAME" ]; then
    ALIAS_NAME="coda"
fi

echo ""
echo "============================================================"
echo -e "  ${BOLD}Installing Coda with:${RESET}"
echo "    Ollama:  http://${OLLAMA_IP}:11434"
echo "    Model:   ${MODEL_NAME}"
echo "    Command: ${ALIAS_NAME}"
echo "============================================================"
echo ""

# --- Step 1: Install Python dependencies ---
echo -e "${BLUE}[1/5]${NC} Installing Python dependencies..."
sudo apt-get install -y python3 python3-pip python3-tk python3-venv python3-nautilus gir1.2-ayatanaappindicator3-0.1 > /dev/null 2>&1
/usr/bin/pip3 install pystray pillow --break-system-packages > /dev/null 2>&1
echo -e "  ${GREEN}✓ Done${NC}"

# --- Step 2: Install Aider ---
echo -e "${BLUE}[2/5]${NC} Installing Aider..."
python3 -m venv ~/aider-env > /dev/null 2>&1
source ~/aider-env/bin/activate
pip install aider-chat > /dev/null 2>&1
echo -e "  ${GREEN}✓ Done${NC}"

# --- Step 3: Set up alias ---
echo -e "${BLUE}[3/5]${NC} Setting up '${ALIAS_NAME}' command..."

ALIAS_LINE="alias ${ALIAS_NAME}='source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://${OLLAMA_IP}:11434 aider --model ollama/${MODEL_NAME}'"

# Remove old coda alias if exists
sed -i '/alias coda=/d' ~/.bashrc

echo "" >> ~/.bashrc
echo "# Coda - Local AI coding assistant" >> ~/.bashrc
echo "$ALIAS_LINE" >> ~/.bashrc

echo -e "  ${GREEN}✓ Done${NC}"

# --- Step 4: Install Nautilus extension ---
echo -e "${BLUE}[4/5]${NC} Installing right-click menu extension..."

sudo mkdir -p /usr/share/nautilus-python/extensions/

sudo tee /usr/share/nautilus-python/extensions/coda_extension.py > /dev/null << PYEOF
import subprocess
import urllib.parse
import gi
gi.require_version('Nautilus', '4.0')
from gi.repository import Nautilus, GObject

class CodaExtension(GObject.GObject, Nautilus.MenuProvider):
    def get_background_items(self, current_folder):
        return []

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        file = files[0]
        if file.get_uri_scheme() != 'file':
            return []
        if not file.is_directory():
            return []
        folder = urllib.parse.unquote(file.get_uri().replace("file://", ""))
        item = Nautilus.MenuItem(
            name="CodaExtension::call_coda",
            label="Call Coda",
            tip="Launch Coda AI in this folder"
        )
        item.connect("activate", self.launch_coda, folder)
        return [item]

    def launch_coda(self, menu, folder):
        cmd = f"cd '{folder}' && source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://${OLLAMA_IP}:11434 aider --model ollama/${MODEL_NAME} ; exec bash"
        subprocess.Popen([
            'gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd
        ])
PYEOF

nautilus -q 2>/dev/null || true
echo -e "  ${GREEN}✓ Done${NC}"

# --- Step 5: Install tray icon ---
echo -e "${BLUE}[5/5]${NC} Installing system tray icon..."

cat > ~/coda-tray.py << TRAYEOF
import subprocess
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw, ImageFont

def create_icon():
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill='white', outline='black', width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "C", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (64 - w) / 2
    y = (64 - h) / 2
    draw.text((x, y), "C", fill='black', font=font)
    return img

def launch_coda(icon, query):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Choose your project folder")
    if folder:
        cmd = f"cd '{folder}' && source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://${OLLAMA_IP}:11434 aider --model ollama/${MODEL_NAME} ; exec bash"
        subprocess.Popen([
            'gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd
        ])

def quit_app(icon, query):
    icon.stop()

icon = pystray.Icon(
    "Coda",
    create_icon(),
    "Coda AI",
    menu=pystray.Menu(
        item('Launch Coda', launch_coda),
        item('Quit', quit_app)
    )
)

icon.run()
TRAYEOF

echo -e "  ${GREEN}✓ Done${NC}"

# --- Auto-start tray on login ---
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/coda-tray.desktop << AUTOEOF
[Desktop Entry]
Type=Application
Name=Coda Tray
Exec=/usr/bin/python3 /home/$USER/coda-tray.py
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
AUTOEOF

# --- Done! ---
echo ""
echo "============================================================"
echo -e "  ${GREEN}${BOLD}✓ Coda installed successfully!${RESET}"
echo "============================================================"
echo ""
echo "  How to use:"
echo ""
echo -e "  ${YELLOW}From the file manager:${NC}"
echo "    Open any project folder → right-click → Call Coda"
echo ""
echo -e "  ${YELLOW}From the terminal:${NC}"
echo "    cd ~/my-project"
echo "    ${ALIAS_NAME}"
echo ""
echo -e "  ${YELLOW}Reload your terminal to activate the command:${NC}"
echo "    source ~/.bashrc"
echo ""
echo "  Enjoy Coda! 🤖"
echo ""
