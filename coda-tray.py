#!/usr/bin/python3
import subprocess
import os
import sys
import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw, ImageFont

CODA_DIR = os.path.expanduser('~/Coda')
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
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    open(RUNNING_FILE, 'w').close()

def remove_lock():
    for f in [LOCK_FILE, RUNNING_FILE]:
        try:
            os.remove(f)
        except:
            pass

if is_already_running():
    sys.exit(0)

write_lock()

# --- Load config ---
def load_config():
    import json
    try:
        with open(os.path.expanduser('~/.config/coda/config.json')) as f:
            return json.load(f)
    except:
        return {
            'ollama_ip': '192.168.2.200',
            'model': 'coda:2.0',
            'provider': 'Ollama (local)'
        }

# --- Toast notification ---
def show_notification(title, message):
    try:
        subprocess.Popen([
            'notify-send',
            f'--icon={os.path.expanduser("~/.local/share/icons/coda.svg")}',
            '--expire-time=3000',
            title, message
        ])
    except:
        pass

# --- Icon ---
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
    h = bbox[3] - bbox[0]
    x = (64 - w) / 2 - 2
    y = (64 - h) / 2 - 4
    draw.text((x, y), "C", fill='black', font=font)
    return img

email_process = None

def launch_coda(icon, query):
    import tkinter as tk
    from tkinter import filedialog
    config = load_config()
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Choose your project folder")
    root.destroy()
    if folder:
        if config.get('provider') == 'Ollama (local)':
            env = f"OLLAMA_API_BASE=http://{config.get('ollama_ip', 'localhost')}:11434"
            model = f"ollama/{config.get('model', 'coda:2.0')}"
        elif config.get('provider') == 'Claude API':
            env = f"ANTHROPIC_API_KEY={config.get('api_key', '')}"
            model = config.get('model', 'claude-sonnet-4-20250514')
        elif config.get('provider') == 'OpenAI':
            env = f"OPENAI_API_KEY={config.get('api_key', '')}"
            model = config.get('model', 'gpt-4o')
        elif config.get('provider') == 'Groq':
            env = f"GROQ_API_KEY={config.get('api_key', '')}"
            model = f"groq/{config.get('model', '')}"
        else:
            env = f"OPENAI_API_BASE={config.get('custom_url', '')}"
            model = config.get('model', '')

        cmd = f"cd '{folder}' && source ~/aider-env/bin/activate && {env} aider --model {model} ; exec bash"
        subprocess.Popen(['gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd])

def launch_email(icon, query):
    global email_process
    if email_process is None or email_process.poll() is not None:
        email_process = subprocess.Popen([
            '/usr/bin/python3', os.path.join(CODA_DIR, 'coda-email.py')
        ])
    else:
        try:
            subprocess.Popen(['wmctrl', '-a', 'Coda Email Assistant'])
        except:
            pass

def open_preferences(icon, query):
    subprocess.Popen([
        '/usr/bin/python3', os.path.join(CODA_DIR, 'coda-preferences.py')
    ])

def quit_app(icon, query):
    remove_lock()
    global email_process
    if email_process and email_process.poll() is None:
        email_process.terminate()
    icon.stop()

tray_icon = pystray.Icon(
    "Coda",
    create_icon(),
    "Coda AI",
    menu=Menu(
        item('Launch Coda', launch_coda),
        item('Email Agent', launch_email),
        Menu.SEPARATOR,
        item('Preferences', open_preferences),
        Menu.SEPARATOR,
        item('Quit', quit_app)
    )
)

def setup(icon):
    icon.visible = True
    show_notification("Coda is running", "Your AI assistant is ready in the system tray.")

tray_icon.run(setup)
