#!/usr/bin/python3
import subprocess
import os
import sys
import json
import threading
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
CODA_DIR = os.path.expanduser('~/Coda')
CONFIG_FILE = os.path.expanduser('~/.config/coda/config.json')
LOCK_FILE = '/tmp/coda-tray.lock'
RUNNING_FILE = '/tmp/coda-running'

# --- Single instance check ---
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
        "email_provider": "Gmail",
        "email": "",
        "app_password": "",
        "imap_server": "imap.gmail.com",
        "smtp_server": "smtp.gmail.com",
        "alias": "coda",
        "refresh_minutes": 5,
        "user_name": ""
    }
    try:
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        defaults.update(data)
    except Exception:
        pass
    return defaults

def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def get_active_provider():
    cfg = load_config()
    return cfg.get("provider", "Ollama (local)")

def set_active_provider(provider):
    cfg = load_config()
    cfg["provider"] = provider
    save_config(cfg)

# --- Build aider launch command based on active provider ---
def build_aider_cmd(folder, cfg):
    provider = cfg.get("provider", "Ollama (local)")
    model = cfg.get("model", "")
    api_key = cfg.get("api_key", "")
    ollama_ip = cfg.get("ollama_ip", "")

    activate = "source ~/aider-env/bin/activate"

    if provider == "Ollama (local)":
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        return f"cd '{folder}' && {activate} && OLLAMA_API_BASE={base_url} aider --model ollama/{model} ; exec bash"

    elif provider == "Gemini":
        return f"cd '{folder}' && {activate} && GEMINI_API_KEY={api_key} aider --model gemini/{model or 'gemini-1.5-pro'} ; exec bash"

    elif provider == "OpenAI":
        return f"cd '{folder}' && {activate} && OPENAI_API_KEY={api_key} aider --model {model or 'gpt-4o'} ; exec bash"

    elif provider == "Claude":
        return f"cd '{folder}' && {activate} && ANTHROPIC_API_KEY={api_key} aider --model {model or 'claude-opus-4-5'} ; exec bash"

    else:
        # Fallback to Ollama
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        return f"cd '{folder}' && {activate} && OLLAMA_API_BASE={base_url} aider --model ollama/{model} ; exec bash"

# --- Icon ---
def create_icon():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill='white', outline='black', width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "C", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[0]
    x = (64 - w) / 2 - 2
    y = (64 - h) / 2 - 4
    draw.text((x, y), "C", fill='black', font=font)
    return img

# --- Toast notification ---
def show_notification(title, message):
    try:
        subprocess.Popen(['notify-send', '-t', '3000', title, message])
    except Exception:
        pass

# --- Launch Coda coding assistant ---
def launch_coda(icon=None, query=None):
    def _pick_and_launch():
        try:
            result = subprocess.run(
                ['zenity', '--file-selection', '--directory',
                 '--title=Choose your project folder', '--filename=' + os.path.expanduser('~/')],
                capture_output=True, text=True
            )
            folder = result.stdout.strip()
            if folder:
                cfg = load_config()
                cmd = build_aider_cmd(folder, cfg)
                provider = cfg.get("provider", "Ollama (local)")
                subprocess.Popen([
                    'gnome-terminal',
                    f'--title=Coda 🤖  [{provider}]',
                    '--', 'bash', '-c', cmd
                ])
        except Exception as e:
            show_notification("Coda Error", str(e))
    threading.Thread(target=_pick_and_launch, daemon=True).start()

# --- Launch Email Agent ---
def launch_email(icon=None, query=None):
    def _launch():
        email_script = os.path.join(CODA_DIR, 'coda-email.py')
        try:
            # If already open, bring to front
            subprocess.run(['wmctrl', '-a', 'Coda Email'], capture_output=True)
        except Exception:
            pass
        subprocess.Popen(['/usr/bin/python3', email_script])
    threading.Thread(target=_launch, daemon=True).start()

# --- Launch Preferences ---
def launch_preferences(icon=None, query=None):
    def _launch():
        pref_script = os.path.join(CODA_DIR, 'coda-preferences.py')
        subprocess.Popen(['/usr/bin/python3', pref_script])
    threading.Thread(target=_launch, daemon=True).start()

# --- Model switcher ---
def make_switch_provider_fn(provider_name):
    """Returns a callback that switches to the given provider."""
    def _switch(icon, query):
        cfg = load_config()
        # If switching to a cloud provider, check if API key is set
        if provider_name != "Ollama (local)":
            api_key = cfg.get("api_key", "").strip()
            if not api_key:
                show_notification(
                    "⚠️  API key missing",
                    f"Open Preferences to add your {provider_name} API key first."
                )
                return
        cfg["provider"] = provider_name
        save_config(cfg)
        icon.menu = build_menu()
        show_notification("Coda", f"Switched to {provider_name}")
    return _switch

def provider_checked(provider_name):
    return get_active_provider() == provider_name

def build_menu():
    active = get_active_provider()

    switch_menu = Menu(
        item('🏠  Ollama (local)',  make_switch_provider_fn('Ollama (local)'),
             checked=lambda i: get_active_provider() == 'Ollama (local)'),
        item('🔵  Gemini',         make_switch_provider_fn('Gemini'),
             checked=lambda i: get_active_provider() == 'Gemini'),
        item('🟢  OpenAI',         make_switch_provider_fn('OpenAI'),
             checked=lambda i: get_active_provider() == 'OpenAI'),
        item('🟠  Claude',         make_switch_provider_fn('Claude'),
             checked=lambda i: get_active_provider() == 'Claude'),
    )

    return Menu(
        item('Launch Coda', launch_coda),
        item('Email Agent', launch_email),
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
    try:
        os.remove(RUNNING_FILE)
    except Exception:
        pass
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass
    icon.stop()

# --- Main ---
def main():
    if is_already_running():
        show_notification("Coda", "Coda is already running")
        sys.exit(0)

    write_lock()

    # Update Nautilus extension path just in case
    try:
        ext = '/usr/share/nautilus-python/extensions/coda_extension.py'
        if os.path.exists(ext):
            with open(ext) as f:
                content = f.read()
            if '/home/sebastian/coda-tray.py' in content or 'coda-launcher' in content:
                pass  # already updated elsewhere
    except Exception:
        pass

    show_notification("Coda is running", "Click the C icon in your taskbar to get started")

    icon_image = create_icon()
    icon = pystray.Icon(
        "Coda",
        icon_image,
        "Coda",
        menu=build_menu()
    )
    icon.run()

if __name__ == '__main__':
    main()
