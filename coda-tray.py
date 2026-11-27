#!/usr/bin/python3
import subprocess
import os
import sys
import atexit
import shutil
import time
import signal
import threading
import pystray
from pystray import MenuItem as item, Menu
import colorsys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coda_common as C

PLATFORM     = C.PLATFORM
LOCK_FILE    = C.LOCK_FILE
RUNNING_FILE = C.RUNNING_FILE   # tells the right-click extension the tray is up

# --- Single instance (tray) ---
# The lock file is held open (and locked) for the whole process lifetime. The
# OS releases the lock automatically when the holder dies, so a stale lock
# never blocks a new start. The PID goes in a separate file, because on
# Windows a locked file can't be read by anyone else.
_lock_fp = None

def is_already_running():
    global _lock_fp
    C.ensure_private_dir(C.RUNTIME_DIR)
    _lock_fp = open(LOCK_FILE, 'a+')
    try:
        if C.WINDOWS:
            import msvcrt
            _lock_fp.seek(0)
            msvcrt.locking(_lock_fp.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True  # another instance holds the lock
    return False

def write_lock():
    os.makedirs(C.MARKER_DIR, exist_ok=True)
    open(RUNNING_FILE, 'w').close()
    with open(C.PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def _cleanup_runtime():
    for p in (RUNNING_FILE, C.PID_FILE):
        try:
            os.remove(p)
        except OSError:
            pass

load_config = C.load_config
save_config = C.save_config

def get_active_provider():
    return load_config().get("provider", "Ollama (local)")

# --- Session counter (marker files written by `coda code`) ---
def get_terminal_count():
    return len(C.live_sessions())

# --- Icon helpers ---
def _draw_C_arc(draw, size, color='black'):
    """Draw a bold C as a geometric arc — no font dependency."""
    cx, cy = size / 2, size / 2
    r  = size * 0.32          # arc centre-line radius
    lw = max(4, int(size / 9)) # stroke width
    box = [cx - r, cy - r, cx + r, cy + r]
    draw.arc(box, start=40, end=320, fill=color, width=lw)

def _draw_C(draw, canvas, border=2):
    p = max(1, border // 2)
    draw.ellipse([p, p, canvas - p, canvas - p],
                 fill='white', outline='black', width=border)
    _draw_C_arc(draw, canvas)

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
    _draw_C_arc(draw, SIZE)
    return img

# --- Notification ---
_icon = None   # the tray icon, once it exists (Windows shows notifications through it)

def show_notification(title, message):
    try:
        if C.WINDOWS:
            if _icon is not None:
                _icon.notify(message, title)
        elif PLATFORM == 'Darwin':
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
    if PLATFORM == 'Darwin':
        return  # Tkinter mainloop poisons NSApplication; pystray can't show icon after

    word     = 'CODA'
    LETTER_W = 7
    LETTER_H = 9
    PIXEL    = 23
    GAP      = PIXEL
    PAD      = PIXEL * 2
    canvas_w = len(word) * LETTER_W * PIXEL + (len(word) - 1) * GAP + PAD * 2
    canvas_h = LETTER_H * PIXEL + PAD * 2

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
            C.open_session_window(folder)
            time.sleep(1)
            if icon:
                icon.icon = create_icon(get_terminal_count())
        except Exception as e:
            show_notification("Coda Error", str(e))
    threading.Thread(target=_pick_and_launch, daemon=True).start()

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
            elif not C.WINDOWS:
                try:
                    subprocess.run(['wmctrl', '-a', 'Coda — Preferences'],
                                   capture_output=True, timeout=2)
                except Exception:
                    pass
            return
        script = os.path.join(C.CODE_DIR, 'coda-preferences.py')
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

def make_switch_engine_fn(engine):
    def _switch(icon, query):
        if not C.find_engine(engine):
            show_notification("Coda", f"{C.ENGINES[engine]['label']} is not installed — "
                                      f"see {C.ENGINES[engine]['url']}")
            return
        cfg = load_config()
        cfg["engine"] = engine
        save_config(cfg)
        icon.menu = build_menu()
        show_notification("Coda", f"Call Coda now opens {C.ENGINES[engine]['label']}")
    return _switch

def _engine_item(key):
    return item(C.ENGINES[key]['label'], make_switch_engine_fn(key), radio=True,
                checked=lambda i: load_config().get('engine', 'aider') == key)

def _provider_item(label, name):
    return item(label, make_switch_provider_fn(name), radio=True,
                checked=lambda i: get_active_provider() == name)

def build_menu():
    cfg = load_config()
    engine_menu = Menu(*[_engine_item(k) for k in C.ENGINES])
    provider_menu = Menu(
        _provider_item('🏠  Ollama (local)', 'Ollama (local)'),
        _provider_item('🔵  Gemini', 'Gemini'),
        _provider_item('🟢  OpenAI', 'OpenAI'),
        _provider_item('🟠  Claude', 'Claude'),
    )
    entries = [
        item('Launch Coda', launch_coda),
        Menu.SEPARATOR,
        item(f'Agent: {C.session_label(cfg)}', None, enabled=False),
        item('Coding Agent', engine_menu),
    ]
    if cfg.get('engine', 'aider') == 'aider':
        entries.append(item('Aider Model', provider_menu))
    entries += [
        Menu.SEPARATOR,
        item('Preferences', launch_preferences),
        Menu.SEPARATOR,
        item('Quit', quit_app),
    ]
    return Menu(*entries)

# --- Quit ---
def _confirm_close_sessions(n):
    import tkinter as tk
    from tkinter import messagebox
    r = tk.Tk()
    r.withdraw()
    s = 's' if n != 1 else ''
    ok = messagebox.askyesno(
        "Quit Coda",
        f"You have {n} Coda session{s} open.\n\nQuit anyway? They will be closed.",
        parent=r)
    r.destroy()
    return ok

def quit_app(icon, query):
    sessions = C.live_sessions()
    if sessions and not _confirm_close_sessions(len(sessions)):
        return
    # Each session is a `coda code` process: on SIGTERM it stops its own aider
    # and exits, which closes its terminal window. Nothing else is touched.
    for pid, _path in sessions:
        C.terminate(pid, force=C.WINDOWS)   # Windows: the whole session, agent included
    for proc in [_prefs_proc]:
        try:
            if proc is not None and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
    _cleanup_runtime()
    icon.stop()
    # Exit code 0 tells the macOS LaunchAgent not to restart us.
    threading.Timer(2.0, lambda: os._exit(0)).start()

# --- macOS: start Ollama if it is installed but not running ---
def _ensure_ollama_mac():
    import urllib.request
    try:
        urllib.request.urlopen('http://localhost:11434', timeout=3)
        return
    except Exception:
        pass
    exe = shutil.which('ollama') or next(
        (p for p in ('/usr/local/bin/ollama', '/opt/homebrew/bin/ollama',
                     '/Applications/Ollama.app/Contents/Resources/ollama')
         if os.access(p, os.X_OK)), None)
    if exe:
        C.detached_popen([exe, 'serve'])

# --- Main ---
def main():
    if is_already_running():
        show_notification("Coda", "Coda is already running")
        sys.exit(0)

    write_lock()
    atexit.register(_cleanup_runtime)
    try:
        show_splash()
    except Exception:
        pass  # splash is cosmetic — don't let it block tray startup

    global _icon
    icon = pystray.Icon("Coda", create_icon(), "Coda", menu=build_menu())
    _icon = icon

    def _on_term(signum, frame):
        _cleanup_runtime()
        try:
            icon.stop()
        finally:
            os._exit(0)
    signal.signal(signal.SIGTERM, _on_term)

    def setup(ic):
        ic.visible = True
        cfg = load_config()
        if PLATFORM == 'Darwin' and cfg.get('engine') == 'aider' \
                and get_active_provider() == 'Ollama (local)':
            threading.Thread(target=_ensure_ollama_mac, daemon=True).start()
        start_badge_monitor(ic)

    icon.run(setup)

if __name__ == '__main__':
    log_path = os.path.join(C.HOME, '.coda-error.log')
    try:
        main()
    except Exception as e:
        import traceback
        with open(log_path, 'a') as _lf:
            import datetime
            _lf.write(f"\n--- {datetime.datetime.now()} ---\n")
            traceback.print_exc(file=_lf)
        raise
