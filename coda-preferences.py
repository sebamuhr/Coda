#!/usr/bin/python3
import tkinter as tk
from tkinter import ttk, messagebox
import os
import signal
import time
import subprocess
import threading

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coda_common as C

PROVIDERS       = C.PROVIDERS
PROVIDER_MODELS = C.PROVIDER_MODELS

PROVIDER_KEY_LABEL = {
    "Ollama (local)": None,
    "Gemini":         "Google AI Studio API Key",
    "OpenAI":         "OpenAI API Key",
    "Claude":         "Anthropic API Key",
}

PROVIDER_KEY_HELP = {
    "Gemini": ("Get a free key at aistudio.google.com", "https://aistudio.google.com/apikey"),
    "OpenAI": ("Get a key at platform.openai.com",      "https://platform.openai.com/api-keys"),
    "Claude": ("Get a key at console.anthropic.com",    "https://console.anthropic.com/settings/keys"),
}

def set_link(label, text, url=None):
    """Turn a label into a clickable link (or back into plain grey text)."""
    import webbrowser
    label.unbind('<Button-1>')
    if url:
        label.config(text=text, foreground='#1a62c9', cursor='hand2', font=('', 9, 'underline'))
        label.bind('<Button-1>', lambda e: webbrowser.open(url))
    else:
        label.config(text=text, foreground='gray', cursor='', font=('', 9))



def apply_theme(root, setting='light'):
    actual = setting
    if setting == 'auto':
        try:
            r = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'color-scheme'],
                capture_output=True, text=True, timeout=2)
            actual = 'dark' if 'dark' in r.stdout.lower() else 'light'
        except Exception:
            actual = 'light'
    style = ttk.Style(root)
    style.theme_use('clam')
    if actual == 'dark':
        BG, BG2, BG3 = '#2b2b2b', '#3c3f41', '#525556'
        FG, SEL      = '#c0c0c0', '#4472c4'
        root.configure(bg=BG)
        for k, v in [('*Background', BG), ('*Foreground', FG),
                     ('*selectBackground', SEL), ('*selectForeground', FG),
                     ('*insertBackground', FG), ('*Text.Background', BG2),
                     ('*Listbox.Background', BG2), ('*Canvas.Background', BG)]:
            root.option_add(k, v, 'interactive')
        s, m = style.configure, style.map
        s('.',                 background=BG,  foreground=FG)
        s('TFrame',            background=BG)
        s('TLabel',            background=BG,  foreground=FG)
        s('TButton',           background=BG2, foreground=FG)
        m('TButton',           background=[('active', BG3), ('pressed', BG)])
        s('TEntry',            fieldbackground=BG2, foreground=FG, insertcolor=FG)
        s('TCombobox',         fieldbackground=BG2, foreground=FG,
                               selectbackground=SEL, arrowcolor=FG)
        m('TCombobox',         fieldbackground=[('readonly', BG2)],
                               foreground=[('readonly', FG)])
        s('TNotebook',         background=BG)
        s('TNotebook.Tab',     background=BG2, foreground=FG, padding=[8, 4])
        m('TNotebook.Tab',     background=[('selected', BG3)])
        s('TLabelframe',       background=BG,  bordercolor=BG3)
        s('TLabelframe.Label', background=BG,  foreground=FG)
        s('TSeparator',        background=BG3)
        s('TScrollbar',        background=BG2, troughcolor=BG, arrowcolor=FG)
        m('TScrollbar',        background=[('active', BG3)])

load_config = C.load_config
save_config = C.save_config

# ─────────────────────────────────────────────
class PreferencesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Coda — Preferences")
        self.root.resizable(True, True)
        self.root.geometry("560x560")
        self.cfg = load_config()
        apply_theme(root, self.cfg.get('theme', 'light'))
        self._build_ui()
        self._load_values()
        self.root.after(50, self._fit_window)

    def _fit_window(self):
        """Grow the window so every tab's content is fully visible (never shrink
        it below what the user chose, never taller than the screen)."""
        self.root.update_idletasks()
        need_w = self.root.winfo_reqwidth()
        need_h = self.root.winfo_reqheight()
        max_h = self.root.winfo_screenheight() - 80
        w = max(self.root.winfo_width(), need_w, 560)
        h = min(max(self.root.winfo_height(), need_h), max_h)
        if (w, h) != (self.root.winfo_width(), self.root.winfo_height()):
            self.root.geometry(f"{w}x{h}")
        self.root.minsize(min(need_w, w), min(need_h, max_h))

    def _build_ui(self):
        # Pack button bar first so it's always anchored to the bottom
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(side='bottom', fill='x', padx=10, pady=(10, 10))
        ttk.Button(btn_frame, text='Save', command=self._save, width=14).pack(side='right')
        ttk.Button(btn_frame, text='Cancel', command=self.root.destroy, width=10).pack(side='right', padx=6)

        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=10, pady=(10, 0))

        self.tab_ai    = ttk.Frame(nb, padding=16)
        self.tab_gen   = ttk.Frame(nb, padding=16)

        nb.add(self.tab_ai,    text='  Call Coda  ')
        nb.add(self.tab_gen,   text='  General  ')

        self._build_ai_tab()
        self._build_general_tab()

    # ── AI Provider tab ──────────────────────────────
    def _build_ai_tab(self):
        f = self.tab_ai

        ttk.Label(f, text="Coding agent", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Label(f, text="Opens when you right-click a folder → Call Coda, or run 'coda'.",
                  foreground='gray', font=('', 9)).grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))

        ttk.Label(f, text="Agent:").grid(row=2, column=0, sticky='w', pady=4)
        self.var_engine = tk.StringVar()
        self._engine_labels = {v['label']: k for k, v in C.ENGINES.items()}
        self.cb_engine = ttk.Combobox(f, textvariable=self.var_engine, state='readonly', width=28,
                                      values=list(self._engine_labels))
        self.cb_engine.grid(row=2, column=1, sticky='ew', pady=4)
        self.cb_engine.bind('<<ComboboxSelected>>', self._on_engine_change)
        self.lbl_engine_status = ttk.Label(f, text="", foreground='gray', font=('', 9), wraplength=440, justify='left')
        self.lbl_engine_status.grid(row=3, column=0, columnspan=2, sticky='w', pady=(0, 8))

        # Aider-only settings (other agents handle their own login and model)
        self.aider_box = ttk.LabelFrame(f, text=" Aider settings ", padding=10)
        self.aider_box.grid(row=4, column=0, columnspan=2, sticky='ew')
        a = self.aider_box

        ttk.Label(a, text="Provider:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_provider = tk.StringVar()
        self.cb_provider = ttk.Combobox(a, textvariable=self.var_provider, values=PROVIDERS, state='readonly', width=28)
        self.cb_provider.grid(row=1, column=1, sticky='ew', pady=4)
        self.cb_provider.bind('<<ComboboxSelected>>', self._on_provider_change)

        self.lbl_ip = ttk.Label(a, text="Ollama Server IP:")
        self.lbl_ip.grid(row=2, column=0, sticky='w', pady=4)
        self.var_ip = tk.StringVar()
        self.ent_ip = ttk.Entry(a, textvariable=self.var_ip, width=30)
        self.ent_ip.grid(row=2, column=1, sticky='ew', pady=4)

        ttk.Label(a, text="Model:").grid(row=3, column=0, sticky='w', pady=4)
        self.var_model = tk.StringVar()
        self.cb_model = ttk.Combobox(a, textvariable=self.var_model, width=28)
        self.cb_model.grid(row=3, column=1, sticky='ew', pady=4)

        self.lbl_key = ttk.Label(a, text="API Key:")
        self.lbl_key.grid(row=4, column=0, sticky='w', pady=4)
        self.var_key = tk.StringVar()
        self.ent_key = ttk.Entry(a, textvariable=self.var_key, show='*', width=30)
        self.ent_key.grid(row=4, column=1, sticky='ew', pady=4)

        self.lbl_key_help = ttk.Label(a, text="", foreground='gray', font=('', 9))
        self.lbl_key_help.grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 6))
        a.columnconfigure(1, weight=1)
        f.columnconfigure(1, weight=1)

    def _engine_key(self):
        return self._engine_labels.get(self.var_engine.get(), 'aider')

    def _on_engine_change(self, event=None):
        key = self._engine_key()
        if key == 'aider':
            self.aider_box.grid()
        else:
            self.aider_box.grid_remove()
        self.lbl_engine_status.config(text="Checking…", foreground='gray')

        def _check():
            exe = C.find_engine(key)
            info = C.ENGINES[key]
            if exe:
                extra = '' if key == 'aider' else '  It uses its own login and model settings.'
                msg, color = f"✓ Found at {exe}.{extra}", 'green'
            else:
                msg, color = f"✗ {info['label']} is not installed — get it at {info['url']}", 'red'
            self.root.after(0, lambda: self.lbl_engine_status.config(text=msg, foreground=color))
        threading.Thread(target=_check, daemon=True).start()

    def _on_provider_change(self, event=None):
        provider = self.var_provider.get()
        models = PROVIDER_MODELS.get(provider, [])
        self.cb_model['values'] = models
        if models and self.var_model.get() not in models:
            self.var_model.set(models[0])

        key_label = PROVIDER_KEY_LABEL.get(provider)
        key_help  = PROVIDER_KEY_HELP.get(provider, "")

        if provider == "Ollama (local)":
            self.lbl_ip.grid()
            self.ent_ip.grid()
            self.lbl_key.grid_remove()
            self.ent_key.grid_remove()
            set_link(self.lbl_key_help, "")
        else:
            self.lbl_ip.grid_remove()
            self.ent_ip.grid_remove()
            self.lbl_key.config(text=key_label + ":")
            self.lbl_key.grid()
            self.ent_key.grid()
            set_link(self.lbl_key_help, *(key_help or ("",)))

    def _build_general_tab(self):
        f = self.tab_gen

        ttk.Label(f, text="General Settings", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Terminal command:").grid(row=2, column=0, sticky='w', pady=4)
        ttk.Label(f, text="coda", font=('TkFixedFont', 10, 'bold')).grid(row=2, column=1, sticky='w', pady=4)
        ttk.Label(f, text="Run 'coda' in any project folder to start a coding session.",
                  foreground='gray', font=('', 9)).grid(row=3, column=0, columnspan=2, sticky='w')

        ttk.Label(f, text="Theme:").grid(row=4, column=0, sticky='w', pady=10)
        self.var_theme = tk.StringVar()
        ttk.Combobox(f, textvariable=self.var_theme, values=['Light', 'Dark', 'Auto'],
                     state='readonly', width=14).grid(row=4, column=1, sticky='w', pady=10)
        ttk.Label(f, text="Restart Coda to apply a theme change", foreground='gray', font=('', 9)).grid(
            row=5, column=0, columnspan=2, sticky='w')

        ttk.Separator(f).grid(row=6, column=0, columnspan=2, sticky='ew', pady=16)

        ttk.Label(f, text="Update", font=('', 11, 'bold')).grid(row=7, column=0, columnspan=2, sticky='w', pady=(0, 6))
        upd_row = tk.Frame(f)
        upd_row.grid(row=8, column=0, columnspan=2, sticky='w')
        self._update_btn = ttk.Button(upd_row, text='Update Coda', command=self._update_coda, width=16)
        self._update_btn.pack(side='left')
        self._update_status = ttk.Label(upd_row, text='', foreground='gray', font=('', 9))
        self._update_status.pack(side='left', padx=10)
        ttk.Label(f, text="Downloads the latest version from GitHub and restarts.",
                  foreground='gray', font=('', 8)).grid(row=9, column=0, columnspan=2, sticky='w', pady=(4, 0))

        ttk.Separator(f).grid(row=10, column=0, columnspan=2, sticky='ew', pady=16)

        ttk.Label(f, text="Uninstall", font=('', 11, 'bold')).grid(row=11, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Button(f, text='🗑  Uninstall Coda', command=self._uninstall,
                   width=20).grid(row=12, column=0, sticky='w')
        ttk.Label(f, text="Removes Coda, its settings and its shortcuts.",
                  foreground='gray', font=('', 8)).grid(row=13, column=0, columnspan=2, sticky='w', pady=(4, 0))

        f.columnconfigure(1, weight=1)

    def _update_coda(self):
        self._update_btn.config(state='disabled')
        self._update_status.config(text='Checking for updates…', foreground='gray')
        threading.Thread(target=self._do_update, daemon=True).start()

    def _coda(self, *args):
        return [sys.executable, os.path.join(C.CODE_DIR, 'coda.py'), *args]

    def _do_update(self):
        def _ui(text, color):
            self.root.after(0, lambda: self._update_status.config(text=text, foreground=color))
            self.root.after(0, lambda: self._update_btn.config(state='normal'))
        try:
            r = subprocess.run(self._coda('update', '--no-restart'),
                               capture_output=True, text=True, timeout=180)
        except Exception as e:
            return _ui(f'Error: {str(e)[:100]}', 'red')
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            return _ui(f'Error: {out.splitlines()[-1][:100] if out else "update failed"}', 'red')
        if 'Already up to date' in out:
            return _ui('Already up to date.', 'gray')
        _ui('Updated!', 'green')
        self.root.after(200, self._ask_restart)

    def _uninstall(self):
        if not messagebox.askyesno(
                "Uninstall Coda",
                "This will permanently remove:\n\n"
                "  •  Your Coda settings\n"
                "  •  The app launcher, autostart and right-click menu\n"
                "  •  The 'coda' terminal command\n"
                "  •  The coding engine (aider) installed for Coda\n\n"
                "A git checkout of Coda's source code is never deleted.\n\n"
                "This cannot be undone. Are you sure?",
                icon='warning'):
            return
        # The uninstaller stops every Coda process — including this window —
        # so it runs detached and reports back with a desktop notification.
        subprocess.Popen(self._coda('uninstall', '--yes'), start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        self.root.destroy()

    # ── Load values ───────────────────────────────────
    def _load_values(self):
        c = self.cfg
        engine = c.get('engine', 'aider')
        self.var_engine.set(C.ENGINES.get(engine, C.ENGINES['aider'])['label'])
        self._on_engine_change()
        self.var_provider.set(c.get('provider', 'Ollama (local)'))
        self.var_ip.set(c.get('ollama_ip', ''))
        self.var_key.set(c.get('api_key', ''))
        self._on_provider_change()
        self.var_model.set(c.get('model', ''))

        self.var_theme.set(c.get('theme', 'light').capitalize())

    # ── Save ──────────────────────────────────────────
    def _save(self):
        self.cfg.update({
            "engine":            self._engine_key(),
            "provider":          self.var_provider.get(),
            "ollama_ip":         self.var_ip.get().strip(),
            "model":             self.var_model.get().strip(),
            "api_key":           self.var_key.get().strip(),
            "theme":             self.var_theme.get().lower(),
        })

        save_config(self.cfg)

        self._ask_restart()

    def _ask_restart(self):
        if messagebox.askyesno(
            "Restart Now",
            "Settings saved.\n\nRestart Coda now to load the changes?",
            default='yes'
        ):
            self._restart_coda()
        else:
            self.root.destroy()

    def _restart_coda(self):
        # Stop the running tray, wait until it has really gone (so its lock is
        # released), then start a fresh one. Never two trays at once.
        try:
            with open(C.LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, signal.SIGTERM)
            for _ in range(50):
                os.kill(old_pid, 0)
                time.sleep(0.1)
        except (OSError, ValueError):
            pass
        subprocess.Popen([sys.executable, os.path.join(C.CODE_DIR, 'coda-tray.py')],
                         start_new_session=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = PreferencesApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
