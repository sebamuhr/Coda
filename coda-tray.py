#!/usr/bin/python3
import subprocess
import os
import sys
import json
import glob
import time
import signal
import threading
import tempfile
import platform
import pystray
from pystray import MenuItem as item, Menu
import colorsys
from PIL import Image, ImageDraw, ImageFont

PLATFORM = platform.system()  # 'Linux' or 'Darwin'

# --- Paths ---
CODA_DIR     = os.path.dirname(os.path.abspath(__file__))
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
    # Do NOT clear existing markers — each terminal manages its own via
    # bash trap on exit.  /tmp is tmpfs so stale markers vanish on reboot.
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

# --- Terminal counter ---
def get_terminal_count():
    if PLATFORM == 'Darwin':
        try:
            return len(glob.glob(os.path.join(MARKER_DIR, 'term_*')))
        except Exception:
            return 0
    try:
        r = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
        return sum(1 for line in r.stdout.splitlines()
                   if len(line.split(None, 3)) >= 4 and
                   (line.split(None, 3)[3].startswith('Coda ·') or
                    line.split(None, 3)[3].startswith('Coda 🤖')))
    except Exception:
        return 0

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
        run = f"OLLAMA_API_BASE={base_url} aider --model ollama_chat/{model}"
    elif provider == "Gemini":
        run = f"GEMINI_API_KEY={api_key} aider --model gemini/{model or 'gemini-1.5-pro'}"
    elif provider == "OpenAI":
        run = f"OPENAI_API_KEY={api_key} aider --model {model or 'gpt-4o'}"
    elif provider == "Claude":
        run = f"ANTHROPIC_API_KEY={api_key} aider --model {model or 'claude-opus-4-5'}"
    else:
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        run = f"OLLAMA_API_BASE={base_url} aider --model ollama_chat/{model}"

    # touch marker on start, remove on any exit (close window, Ctrl-C, etc.)
    # trailing 'bash' (not exec bash) keeps terminal open after aider exits
    # and ensures the outer shell runs the EXIT trap when window is closed
    return (
        f"mkdir -p {MARKER_DIR} && "
        f"touch '{marker}' && "
        f"trap 'rm -f \"{marker}\"' EXIT HUP INT TERM && "
        f"cd '{folder}' && {activate} && {run} ; bash"
    )

# --- Icon helpers ---
def _ithaca(size):
    path = os.path.join(CODA_DIR, 'ithaca-font', 'Ithaca-LVB75.ttf')
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def _draw_C(draw, canvas, font_size, border=2):
    p = max(1, border // 2)
    draw.ellipse([p, p, canvas - p, canvas - p],
                 fill='white', outline='black', width=border)
    font = _ithaca(font_size)
    bb = draw.textbbox((0, 0), 'C', font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    x = (canvas - w) / 2 - bb[0] + canvas * 0.03  # slight rightward optical shift
    y = (canvas - h) / 2 - bb[1]
    draw.text((x, y), 'C', fill='black', font=font)

# --- Icon (fill level: 0=white, 1=green sliver, 10=full red) ---
def create_icon(count=0):
    SIZE = 64
    t = min(max(count, 0), 10) / 10.0

    base = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(base).ellipse([2, 2, 62, 62], fill='white')

    if t > 0:
        hue = (1 - t) * 120 / 360.0
        rc, gc, bc = colorsys.hsv_to_rgb(hue, 0.90, 0.88)
        fill_color = (int(rc * 255), int(gc * 255), int(bc * 255), 255)

        fill_h   = max(6, int(60 * t))
        fill_top = 62 - fill_h

        overlay = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
        ov = ImageDraw.Draw(overlay)
        ov.ellipse([2, 2, 62, 62], fill=fill_color)
        if fill_top > 2:
            ov.rectangle([0, 0, SIZE, fill_top], fill=(0, 0, 0, 0))

        img = Image.alpha_composite(base, overlay)
    else:
        img = base

    draw = ImageDraw.Draw(img)
    draw.ellipse([1, 1, 63, 63], outline='black', width=2)
    font = _ithaca(54)
    try:
        draw.text((SIZE / 2 + SIZE * 0.03, SIZE / 2), 'C', fill='black', font=font, anchor='mm')
    except TypeError:
        bb = draw.textbbox((0, 0), 'C', font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        draw.text(((SIZE - w) / 2 - bb[0] + SIZE * 0.03,
                   (SIZE - h) / 2 - bb[1]), 'C', fill='black', font=font)
    return img

def generate_desktop_icon():
    if PLATFORM == 'Darwin':
        return
    SIZE = 256
    img  = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    _draw_C(ImageDraw.Draw(img), SIZE, 185, border=8)
    img.save(os.path.expanduser('~/.local/share/icons/coda.png'))

# --- Notification ---
def show_notification(title, message):
    try:
        if PLATFORM == 'Darwin':
            t = title.replace('"', '\\"')
            m = message.replace('"', '\\"')
            subprocess.Popen(['osascript', '-e',
                f'display notification "{m}" with title "{t}"'])
        else:
            subprocess.Popen(['notify-send', '-t', '3000', title, message])
    except Exception:
        pass

# --- Splash letter bitmaps (7×9 pixel grid) ---
_SPLASH_LETTERS = {
    'C': ['.#####.',
          '#######',
          '##.....',
          '##.....',
          '##.....',
          '##.....',
          '##.....',
          '#######',
          '.#####.'],
    'O': ['.#####.',
          '#######',
          '##...##',
          '##...##',
          '##...##',
          '##...##',
          '##...##',
          '#######',
          '.#####.'],
    'D': ['######.',
          '#######',
          '##...##',
          '##...##',
          '##...##',
          '##...##',
          '##...##',
          '#######',
          '######.'],
    'A': ['..###..',
          '.#####.',
          '.##.##.',
          '.##.##.',
          '#######',
          '##...##',
          '##...##',
          '##...##',
          '##...##'],
}

# --- Startup splash ---
def show_splash():
    word     = 'CODA'
    LETTER_W = 7
    LETTER_H = 9
    PIXEL    = 23
    GAP      = PIXEL
    PAD      = PIXEL * 2
    canvas_w = len(word) * LETTER_W * PIXEL + (len(word) - 1) * GAP + PAD * 2
    canvas_h = LETTER_H * PIXEL + PAD * 2

    if PLATFORM == 'Darwin':
        try:
            import tkinter as tk
        except Exception:
            return

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.attributes('-alpha', 0.0)
        root.configure(bg='black')
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f'{canvas_w}x{canvas_h}+{(sw - canvas_w)//2}+{(sh - canvas_h)//2}')

        cv = tk.Canvas(root, width=canvas_w, height=canvas_h,
                       bg='black', highlightthickness=0)
        cv.pack()

        x_off = PAD
        for letter in word:
            for row_i, row in enumerate(_SPLASH_LETTERS.get(letter, [])):
                for col_i, ch in enumerate(row):
                    if ch == '#':
                        px = x_off + col_i * PIXEL
                        py = PAD   + row_i * PIXEL
                        pw = PIXEL - 2
                        cv.create_rectangle(px, py, px + pw, py + pw,
                                            fill='white', outline='')
            x_off += LETTER_W * PIXEL + GAP

        alpha   = [0.0]
        phase   = ['fadein']
        elapsed = [0]
        INTERVAL, FADE_MS, HOLD_MS = 33, 500, 2500

        def tick():
            elapsed[0] += INTERVAL
            if phase[0] == 'fadein':
                alpha[0] = min(1.0, elapsed[0] / FADE_MS)
                if elapsed[0] >= FADE_MS:
                    phase[0] = 'hold'; elapsed[0] = 0
            elif phase[0] == 'hold':
                alpha[0] = 1.0
                if elapsed[0] >= HOLD_MS:
                    phase[0] = 'fadeout'; elapsed[0] = 0
            elif phase[0] == 'fadeout':
                alpha[0] = max(0.0, 1.0 - elapsed[0] / FADE_MS)
                if elapsed[0] >= FADE_MS:
                    root.destroy()
                    return
            root.attributes('-alpha', alpha[0])
            root.after(INTERVAL, tick)

        tick()
        root.mainloop()
        return

    # GTK splash (Linux)
    try:
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk, GLib
        import cairo
    except Exception:
        return

    win = Gtk.Window()
    win.set_decorated(False)
    win.set_app_paintable(True)
    win.set_skip_taskbar_hint(True)
    win.set_skip_pager_hint(True)
    win.set_keep_above(True)
    win.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
    win.set_default_size(canvas_w, canvas_h)
    win.set_position(Gtk.WindowPosition.CENTER)

    visual = win.get_screen().get_rgba_visual()
    if visual:
        win.set_visual(visual)

    alpha_val = [0.0]

    def on_draw(widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        x_off = PAD
        for letter in word:
            for row_i, row in enumerate(_SPLASH_LETTERS.get(letter, [])):
                for col_i, ch in enumerate(row):
                    if ch == '#':
                        px = x_off + col_i * PIXEL
                        py = PAD   + row_i * PIXEL
                        pw = PIXEL - 2
                        ph = PIXEL - 2
                        cr.set_source_rgba(1, 1, 1, alpha_val[0])
                        cr.rectangle(px - 1, py - 1, pw + 2, ph + 2)
                        cr.fill()
                        cr.set_source_rgba(0, 0, 0, alpha_val[0])
                        cr.rectangle(px, py, pw, ph)
                        cr.fill()
            x_off += LETTER_W * PIXEL + GAP

    win.connect('draw', on_draw)

    FADE_MS  = 500
    HOLD_MS  = 2500
    INTERVAL = 33
    phase    = ['fadein']
    elapsed  = [0]

    def tick():
        elapsed[0] += INTERVAL
        if phase[0] == 'fadein':
            alpha_val[0] = min(1.0, elapsed[0] / FADE_MS)
            if elapsed[0] >= FADE_MS:
                phase[0] = 'hold'
                elapsed[0] = 0
        elif phase[0] == 'hold':
            alpha_val[0] = 1.0
            if elapsed[0] >= HOLD_MS:
                phase[0] = 'fadeout'
                elapsed[0] = 0
        elif phase[0] == 'fadeout':
            alpha_val[0] = max(0.0, 1.0 - elapsed[0] / FADE_MS)
            if elapsed[0] >= FADE_MS:
                win.destroy()
                Gtk.main_quit()
                return False
        win.queue_draw()
        return True

    win.show_all()
    GLib.timeout_add(INTERVAL, tick)
    Gtk.main()

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
            if PLATFORM == 'Darwin':
                # filedialog calls NSOpenPanel which must run on the main thread;
                # osascript runs in its own process so there are no thread restrictions
                r = subprocess.run(
                    ['osascript', '-e',
                     'set f to choose folder with prompt "Choose your project folder:"\n'
                     'return POSIX path of f'],
                    capture_output=True, text=True
                )
                if r.returncode != 0:
                    return
                folder = r.stdout.strip().rstrip('/')
            else:
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
            if PLATFORM == 'Darwin':
                fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='coda_launch_')
                with os.fdopen(fd, 'w') as f:
                    f.write(f'#!/bin/bash\nprintf "\\033]0;Coda · {provider}\\007"\n{cmd}\n')
                os.chmod(script_path, 0o755)
                subprocess.Popen([
                    'osascript', '-e',
                    f'tell application "Terminal" to do script "{script_path}"'
                ])
            else:
                subprocess.Popen([
                    'gnome-terminal',
                    f'--title=Coda · {provider}',
                    '--', 'bash', '-c', cmd
                ])
            time.sleep(1)
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
                os.kill(_email_proc.pid, signal.SIGUSR1)
            except Exception:
                pass
            return
        script = os.path.join(CODA_DIR, 'coda-email.py')
        _email_proc = subprocess.Popen([sys.executable, script])
    threading.Thread(target=_launch, daemon=True).start()

# --- Launch Preferences (single instance) ---
_prefs_proc = None

def launch_preferences(icon=None, query=None):
    global _prefs_proc
    def _launch():
        global _prefs_proc
        if _prefs_proc is not None and _prefs_proc.poll() is None:
            if PLATFORM == 'Darwin':
                try:
                    subprocess.run([
                        'osascript', '-e',
                        'tell application "System Events"\n'
                        'set frontmost of (first process whose name contains "python") to true\n'
                        'end tell'
                    ], capture_output=True, timeout=2)
                except Exception:
                    pass
            else:
                try:
                    subprocess.run(['wmctrl', '-a', 'Coda — Preferences'],
                                   capture_output=True, timeout=2)
                except Exception:
                    pass
            return
        script = os.path.join(CODA_DIR, 'coda-preferences.py')
        _prefs_proc = subprocess.Popen([sys.executable, script])
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
    if PLATFORM == 'Darwin':
        coda_wins = glob.glob(os.path.join(MARKER_DIR, 'term_*'))
        if coda_wins:
            import tkinter as tk
            from tkinter import messagebox
            _r = tk.Tk()
            _r.withdraw()
            n = len(coda_wins)
            s = 's' if n != 1 else ''
            ok = messagebox.askyesno(
                "Quit Coda",
                f"You have {n} Coda terminal{s} open.\n\nQuit anyway? All terminals will be closed.",
                parent=_r)
            _r.destroy()
            if not ok:
                return
        subprocess.run(['pkill', '-f', 'aider'], capture_output=True)
    else:
        coda_wins = []
        try:
            r = subprocess.run(['wmctrl', '-l'], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    title = parts[3]
                    if title.startswith('Coda ·') or title.startswith('Coda 🤖'):
                        coda_wins.append(parts[0])
        except Exception:
            pass

        if coda_wins:
            import tkinter as tk
            from tkinter import messagebox
            _r = tk.Tk()
            _r.withdraw()
            n = len(coda_wins)
            s = 's' if n != 1 else ''
            ok = messagebox.askyesno(
                "Quit Coda",
                f"You have {n} Coda terminal{s} open.\n\nQuit anyway? All terminals will be closed.",
                parent=_r)
            _r.destroy()
            if not ok:
                return
        for wid in coda_wins:
            subprocess.run(['wmctrl', '-ic', wid], capture_output=True)

    for proc in [_email_proc, _prefs_proc]:
        try:
            if proc is not None and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
    subprocess.run(['pkill', '-f', 'coda-email.py'],       capture_output=True)
    subprocess.run(['pkill', '-f', 'coda-preferences.py'], capture_output=True)
    for f in [RUNNING_FILE, LOCK_FILE]:
        try: os.remove(f)
        except Exception: pass
    icon.stop()
    os.kill(os.getpid(), signal.SIGTERM)

# --- Main ---
def main():
    if is_already_running():
        show_notification("Coda", "Coda is already running")
        sys.exit(0)

    write_lock()
    generate_desktop_icon()
    show_splash()

    icon = pystray.Icon("Coda", create_icon(), "Coda", menu=build_menu())

    def setup(ic):
        ic.visible = True
        start_badge_monitor(ic)

    icon.run(setup)

if __name__ == '__main__':
    main()
