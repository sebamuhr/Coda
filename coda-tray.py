#!/usr/bin/python3
import subprocess
import os
import sys
import json
import glob
import time
import threading
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
CODA_DIR     = os.path.expanduser('~/Coda')
CONFIG_FILE  = os.path.expanduser('~/.config/coda/config.json')
LOCK_FILE    = '/tmp/coda-tray.lock'
RUNNING_FILE = '/tmp/coda-running'
MARKER_DIR   = '/tmp/coda_terminals'   # one file per open coding terminal

# --- Single instance (tray) ---
def is_already_running():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            pass
    return False

def write_lock():
    os.makedirs(MARKER_DIR, exist_ok=True)
    # Remove stale terminal markers from previous sessions
    for f in glob.glob(os.path.join(MARKER_DIR, 'term_*')):
        try:
            os.remove(f)
        except Exception:
            pass
    open(RUNNING_FILE, 'w').close()
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

# --- Config ---
def load_config():
    defaults = {
        "provider": "Ollama (local)",
        "ollama_ip": "",
        "model": "",
        "api_key": "",
        "custom_url": "",
        "alias": "coda",
    }
    try:
        with open(CONFIG_FILE) as f:
            defaults.update(json.load(f))
    except Exception:
        pass
    return defaults

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def get_active_provider():
    return load_config().get("provider", "Ollama (local)")

# --- Terminal counter (marker files) ---
def get_terminal_count():
    return len(glob.glob(os.path.join(MARKER_DIR, 'term_*')))

def new_marker():
    os.makedirs(MARKER_DIR, exist_ok=True)
    path = os.path.join(MARKER_DIR, f'term_{os.getpid()}_{int(time.time())}')
    return path

# --- Aider command builder ---
def build_aider_cmd(folder, cfg, marker):
    provider  = cfg.get("provider", "Ollama (local)")
    model     = cfg.get("model", "")
    api_key   = cfg.get("api_key", "")
    ollama_ip = cfg.get("ollama_ip", "")
    activate  = "source ~/aider-env/bin/activate"

    if provider == "Ollama (local)":
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        run = f"OLLAMA_API_BASE={base_url} aider --model ollama/{model}"
    elif provider == "Gemini":
        run = f"GEMINI_API_KEY={api_key} aider --model gemini/{model or 'gemini-1.5-pro'}"
    elif provider == "OpenAI":
        run = f"OPENAI_API_KEY={api_key} aider --model {model or 'gpt-4o'}"
    elif provider == "Claude":
        run = f"ANTHROPIC_API_KEY={api_key} aider --model {model or 'claude-opus-4-5'}"
    else:
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        run = f"OLLAMA_API_BASE={base_url} aider --model ollama/{model}"

    # touch marker on start, remove on any exit (close window, Ctrl-C, etc.)
    # trailing 'bash' (not exec bash) keeps terminal open after aider exits
    # and ensures the outer shell runs the EXIT trap when window is closed
    return (
        f"mkdir -p {MARKER_DIR} && "
        f"touch '{marker}' && "
        f"trap 'rm -f \"{marker}\"' EXIT HUP INT TERM && "
        f"cd '{folder}' && {activate} && {run} ; bash"
    )

# --- Icon (with optional red badge showing terminal count) ---
def create_icon(count=0):
    img  = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill='white', outline='black', width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "C", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[0]
    draw.text(((64 - w) / 2 - 2, (64 - h) / 2 - 4), "C", fill='black', font=font)

    if count > 0:
        badge = str(min(count, 9))
        try:
            bfont = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except Exception:
            bfont = ImageFont.load_default()
        draw.ellipse([40, 40, 62, 62], fill='#e53935', outline='white', width=1)
        bb = draw.textbbox((0, 0), badge, font=bfont)
        bw, bh = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((51 - bw / 2, 51 - bh / 2 - 1), badge, fill='white', font=bfont)

    return img

# --- Notification ---
def show_notification(title, message):
    try:
        subprocess.Popen(['notify-send', '-t', '3000', title, message])
    except Exception:
        pass

# --- Badge monitor: updates icon every 3 s ---
def start_badge_monitor(icon):
    last = [0]
    def _loop():
        while True:
            time.sleep(3)
            count = get_terminal_count()
            if count != last[0]:
                last[0] = count
                icon.icon = create_icon(count)
    threading.Thread(target=_loop, daemon=True).start()

# --- Launch Coda coding assistant (unlimited instances, counted) ---
def launch_coda(icon=None, query=None):
    def _pick_and_launch():
        try:
            import tkinter as tk
            from tkinter import filedialog, ttk
            root = tk.Tk()
            root.withdraw()
            ttk.Style(root).theme_use('clam')
            folder = filedialog.askdirectory(
                title="Coda — Choose your project folder",
                initialdir=os.path.expanduser('~/'),
                parent=root,
            )
            root.destroy()
            if not folder:
                return
            cfg      = load_config()
            marker   = new_marker()
            cmd      = build_aider_cmd(folder, cfg, marker)
            provider = cfg.get("provider", "Ollama (local)")
            subprocess.Popen([
                'gnome-terminal',
                f'--title=Coda · {provider}',
                '--', 'bash', '-c', cmd
            ])
            time.sleep(1)   # let the terminal open before refreshing count
            if icon:
                icon.icon = create_icon(get_terminal_count())
        except Exception as e:
            show_notification("Coda Error", str(e))
    threading.Thread(target=_pick_and_launch, daemon=True).start()

# --- Launch Email Agent (single instance) ---
_email_proc = None

def launch_email(icon=None, query=None):
    global _email_proc
    def _launch():
        global _email_proc
        if _email_proc is not None and _email_proc.poll() is None:
            try:
                subprocess.run(['wmctrl', '-a', 'Coda — Email Agent'],
                               capture_output=True, timeout=2)
            except Exception:
                pass
            return
        script = os.path.join(CODA_DIR, 'coda-email.py')
        _email_proc = subprocess.Popen(['/usr/bin/python3', script])
    threading.Thread(target=_launch, daemon=True).start()

# --- Launch Preferences (single instance) ---
_prefs_proc = None

def launch_preferences(icon=None, query=None):
    global _prefs_proc
    def _launch():
        global _prefs_proc
        if _prefs_proc is not None and _prefs_proc.poll() is None:
            try:
                subprocess.run(['wmctrl', '-a', 'Coda — Preferences'],
                               capture_output=True, timeout=2)
            except Exception:
                pass
            return
        script = os.path.join(CODA_DIR, 'coda-preferences.py')
        _prefs_proc = subprocess.Popen(['/usr/bin/python3', script])
    threading.Thread(target=_launch, daemon=True).start()

# --- Model switcher ---
def make_switch_provider_fn(provider_name):
    def _switch(icon, query):
        cfg = load_config()
        if provider_name != "Ollama (local)" and not cfg.get("api_key", "").strip():
            show_notification("⚠️  API key missing",
                              f"Open Preferences to add your {provider_name} API key first.")
            return
        cfg["provider"] = provider_name
        save_config(cfg)
        icon.menu = build_menu()
        show_notification("Coda", f"Switched to {provider_name}")
    return _switch

def build_menu():
    active = get_active_provider()
    switch_menu = Menu(
        item('🏠  Ollama (local)', make_switch_provider_fn('Ollama (local)'),
             checked=lambda i: get_active_provider() == 'Ollama (local)'),
        item('🔵  Gemini',        make_switch_provider_fn('Gemini'),
             checked=lambda i: get_active_provider() == 'Gemini'),
        item('🟢  OpenAI',        make_switch_provider_fn('OpenAI'),
             checked=lambda i: get_active_provider() == 'OpenAI'),
        item('🟠  Claude',        make_switch_provider_fn('Claude'),
             checked=lambda i: get_active_provider() == 'Claude'),
    )
    return Menu(
        item('Launch Coda',  launch_coda),
        item('Email Agent',  launch_email),
        Menu.SEPARATOR,
        item(f'Model: {active}', None, enabled=False),
        item('Switch Model', switch_menu),
        Menu.SEPARATOR,
        item('Preferences', launch_preferences),
        Menu.SEPARATOR,
        item('Quit', quit_app),
    )

# --- Quit ---
def quit_app(icon, query):
    for f in [RUNNING_FILE, LOCK_FILE]:
        try:
            os.remove(f)
        except Exception:
            pass
    icon.stop()

# --- Main ---
def main():
    if is_already_running():
        show_notification("Coda", "Coda is already running")
        sys.exit(0)

    write_lock()
    show_notification("Coda is running", "Click the C icon in your taskbar to get started")

    icon = pystray.Icon("Coda", create_icon(), "Coda", menu=build_menu())

    def setup(ic):
        ic.visible = True
        start_badge_monitor(ic)

    icon.run(setup)

if __name__ == '__main__':
    main()
