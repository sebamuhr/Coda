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
    "Gemini": "Get a free key at aistudio.google.com",
    "OpenAI": "Get a key at platform.openai.com",
    "Claude": "Get a key at console.anthropic.com",
}

EMAIL_PROVIDERS = ["Gmail", "Outlook", "Yahoo", "Other"]
EMAIL_IMAP = {
    "Gmail":   ("imap.gmail.com",  "smtp.gmail.com"),
    "Outlook": ("imap-mail.outlook.com", "smtp-mail.outlook.com"),
    "Yahoo":   ("imap.mail.yahoo.com",   "smtp.mail.yahoo.com"),
    "Other":   ("", ""),
}

# --- Privacy warning shown when cloud provider chosen for email ---
EMAIL_PRIVACY_WARNING = (
    "⚠️  Privacy Notice\n\n"
    "You are selecting a cloud AI provider for the Email Agent.\n"
    "Your email content will be sent to an external server to generate replies.\n\n"
    "Make sure you are comfortable with this before continuing.\n\n"
    "Alternatively, set the Email Agent to use Ollama (local) in the AI Provider tab\n"
    "so your emails never leave your machine."
)

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

    def _build_ui(self):
        # Pack button bar first so it's always anchored to the bottom
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(side='bottom', fill='x', padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text='Save', command=self._save, width=14).pack(side='right')
        ttk.Button(btn_frame, text='Cancel', command=self.root.destroy, width=10).pack(side='right', padx=6)

        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=10, pady=(10, 0))

        self.tab_ai    = ttk.Frame(nb, padding=16)
        self.tab_email = ttk.Frame(nb, padding=16)
        self.tab_gen   = ttk.Frame(nb, padding=16)

        nb.add(self.tab_ai,    text='  Call Coda  ')
        nb.add(self.tab_email, text='  Email  ')
        nb.add(self.tab_gen,   text='  General  ')

        self._build_ai_tab()
        self._build_email_tab()
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
            self.lbl_key_help.config(text="")
        else:
            self.lbl_ip.grid_remove()
            self.ent_ip.grid_remove()
            self.lbl_key.config(text=key_label + ":")
            self.lbl_key.grid()
            self.ent_key.grid()
            self.lbl_key_help.config(text=key_help)

    # ── Email tab ─────────────────────────────────────
    def _build_email_tab(self):
        f = self.tab_email

        self.var_email_on = tk.BooleanVar(value=True)
        self._email_on_cb = ttk.Checkbutton(
            f, text="Use the Email Agent  (off: hidden from the tray menu)",
            variable=self.var_email_on, command=self._on_email_toggle)
        self._email_on_cb.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        ttk.Label(f, text="Email Account", font=('', 11, 'bold')).grid(row=1, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Email Provider:").grid(row=2, column=0, sticky='w', pady=4)
        self.var_email_prov = tk.StringVar()
        self.cb_email_prov = ttk.Combobox(f, textvariable=self.var_email_prov, values=EMAIL_PROVIDERS, state='readonly', width=28)
        self.cb_email_prov.grid(row=2, column=1, sticky='ew', pady=4)
        self.cb_email_prov.bind('<<ComboboxSelected>>', self._on_email_provider_change)

        ttk.Label(f, text="Email Address:").grid(row=3, column=0, sticky='w', pady=4)
        self.var_email = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_email, width=30).grid(row=3, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="App Password:").grid(row=4, column=0, sticky='w', pady=4)
        self.var_app_pw = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_app_pw, show='*', width=30).grid(row=4, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="⚠ Not your Gmail password — create one at:\n"
                          "myaccount.google.com → Security → 2-Step Verification → App Passwords",
                  foreground='gray', font=('', 8)).grid(
                      row=5, column=0, columnspan=2, sticky='w', pady=(0, 6))

        ttk.Label(f, text="IMAP Server:").grid(row=6, column=0, sticky='w', pady=4)
        self.var_imap = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_imap, width=30).grid(row=6, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="SMTP Server:").grid(row=7, column=0, sticky='w', pady=4)
        self.var_smtp = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_smtp, width=30).grid(row=7, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="Emails to sync:").grid(row=8, column=0, sticky='w', pady=4)
        self.var_sync_count = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_sync_count, width=8).grid(row=8, column=1, sticky='w', pady=4)

        ttk.Label(f, text="Auto-refresh (minutes):").grid(row=9, column=0, sticky='w', pady=4)
        self.var_refresh = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_refresh, width=8).grid(row=9, column=1, sticky='w', pady=4)

        ttk.Separator(f).grid(row=10, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(f, text="Email AI", font=('', 11, 'bold')).grid(row=11, column=0, columnspan=2, sticky='w', pady=(0,6))
        ttk.Label(f, text="Writes with:").grid(row=12, column=0, sticky='w', pady=4)
        self.var_email_ai = tk.StringVar()
        self._email_ai_labels = {v['label']: k for k, v in C.EMAIL_AI.items()}
        self.cb_email_ai = ttk.Combobox(f, textvariable=self.var_email_ai, state='readonly', width=28,
                                        values=list(self._email_ai_labels))
        self.cb_email_ai.grid(row=12, column=1, sticky='ew', pady=4)
        self.cb_email_ai.bind('<<ComboboxSelected>>', self._on_email_ai_selected)
        self._email_ai_current = 'local'

        # Local model (default)
        self.local_box = ttk.Frame(f)
        self.local_box.grid(row=13, column=0, columnspan=2, sticky='ew')
        lb = self.local_box
        ttk.Label(lb, text="Ollama IP:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_email_ollama_ip = tk.StringVar()
        email_ip_row = ttk.Frame(lb)
        email_ip_row.grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Entry(email_ip_row, textvariable=self.var_email_ollama_ip, width=22).pack(side='left')
        ttk.Button(email_ip_row, text='↺ Check', width=8,
                   command=self._check_model_status).pack(side='left', padx=(6, 0))
        ttk.Label(lb, text="Status:").grid(row=2, column=0, sticky='w', pady=4)
        self._model_status_lbl = ttk.Label(lb, text="Checking...", foreground='gray')
        self._model_status_lbl.grid(row=2, column=1, sticky='w', pady=4)
        self._pull_btn = ttk.Button(lb, text='⬇  Pull Model', command=self._pull_model, width=16)
        self._pull_btn.grid(row=3, column=1, sticky='w', pady=(0, 4))
        self._pull_btn.grid_remove()
        self._pull_progress = ttk.Label(lb, text='', foreground='gray', font=('', 8))
        self._pull_progress.grid(row=4, column=0, columnspan=2, sticky='w')
        self._pull_progress.grid_remove()
        ttk.Label(lb, text="Private: your emails never leave your computer or your own server.",
                  foreground='gray', font=('', 8)).grid(row=5, column=0, columnspan=2, sticky='w')
        lb.columnconfigure(1, weight=1)

        # Cloud model (opt-in)
        self.cloud_box = ttk.Frame(f)
        self.cloud_box.grid(row=14, column=0, columnspan=2, sticky='ew')
        cb = self.cloud_box
        ttk.Label(cb, text="Model:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_email_ai_model = tk.StringVar()
        self.cb_email_ai_model = ttk.Combobox(cb, textvariable=self.var_email_ai_model, width=28)
        self.cb_email_ai_model.grid(row=1, column=1, sticky='ew', pady=4)
        ttk.Label(cb, text="API Key:").grid(row=2, column=0, sticky='w', pady=4)
        self.var_email_ai_key = tk.StringVar()
        ttk.Entry(cb, textvariable=self.var_email_ai_key, show='*', width=30).grid(row=2, column=1, sticky='ew', pady=4)
        self.lbl_email_ai_keyhelp = ttk.Label(cb, text="", foreground='gray', font=('', 8))
        self.lbl_email_ai_keyhelp.grid(row=3, column=0, columnspan=2, sticky='w')
        self.lbl_cloud_warning = tk.Label(cb, text="", fg='#b00020', font=('', 9, 'bold'),
                                          wraplength=470, justify='left', anchor='w')
        self.lbl_cloud_warning.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        cb.columnconfigure(1, weight=1)

        f.columnconfigure(1, weight=1)

    def _on_email_toggle(self):
        on = self.var_email_on.get()
        def walk(w):
            for c in w.winfo_children():
                if c is self._email_on_cb:
                    continue
                if isinstance(c, ttk.Widget) and hasattr(c, 'state'):
                    try:
                        c.state(['!disabled'] if on else ['disabled'])
                    except tk.TclError:
                        pass
                elif not isinstance(c, (tk.Frame, ttk.Frame)):
                    try:
                        c.configure(state='normal' if on else 'disabled')
                    except tk.TclError:
                        pass
                walk(c)
        walk(self.tab_email)

    def _email_ai_key(self):
        return self._email_ai_labels.get(self.var_email_ai.get(), 'local')

    def _on_email_ai_selected(self, event=None):
        ai = self._email_ai_key()
        if ai != 'local' and self._email_ai_current == 'local':
            if not messagebox.askyesno(
                    "Send your emails to the cloud?",
                    "⚠  Privacy warning\n\n" + C.email_cloud_warning(ai) +
                    "\n\nUse " + C.EMAIL_AI[ai]['label'] + " for writing emails anyway?",
                    icon='warning', default='no', parent=self.root):
                self.var_email_ai.set(C.EMAIL_AI['local']['label'])
                ai = 'local'
        self._email_ai_current = ai
        self._show_email_ai(ai)

    def _show_email_ai(self, ai):
        if ai == 'local':
            self.cloud_box.grid_remove()
            self.local_box.grid()
            return
        self.local_box.grid_remove()
        self.cloud_box.grid()
        models = C.EMAIL_AI_MODELS[ai]
        self.cb_email_ai_model['values'] = models
        if self.var_email_ai_model.get() not in models:
            self.var_email_ai_model.set(models[0])
        help_url = {'claude': 'console.anthropic.com', 'gemini': 'aistudio.google.com',
                    'openai': 'platform.openai.com'}[ai]
        same = self.var_provider.get() == C.EMAIL_AI_CODING_PROVIDER[ai]
        self.lbl_email_ai_keyhelp.config(
            text=f"Get a key at {help_url}" + ("  ·  leave empty to reuse the key from the Call Coda tab" if same else ""))
        self.lbl_cloud_warning.config(text="⚠  " + C.email_cloud_warning(ai).split("\n\n")[0])

    def _on_email_provider_change(self, event=None):
        imap, smtp = EMAIL_IMAP.get(self.var_email_prov.get(), ("", ""))
        self.var_imap.set(imap)
        self.var_smtp.set(smtp)

    def _email_host(self):
        return C.normalize_host(self.var_email_ollama_ip.get())

    def _check_model_status(self):
        self._model_status_lbl.config(text="Checking…", foreground='gray')
        self._pull_btn.grid_remove()
        self._pull_progress.config(text='')
        host = self._email_host()

        def _check():
            try:
                found = C.email_model_installed(host)
            except OSError:
                url = C.ollama_url(host)
                self.root.after(0, lambda: self._model_status_lbl.config(
                    text=f"✗ Ollama not reachable at {url}", foreground='red'))
                return
            if found:
                self.root.after(0, lambda: self._model_status_lbl.config(text="✓ Ready", foreground='green'))
            else:
                self.root.after(0, lambda: self._model_status_lbl.config(text="✗ Not installed", foreground='red'))
                self.root.after(0, self._pull_btn.grid)

        threading.Thread(target=_check, daemon=True).start()

    def _pull_model(self):
        self._pull_btn.config(state='disabled')
        self._pull_progress.grid()
        host = self._email_host()

        def _status(msg):
            self.root.after(0, lambda: self._pull_progress.config(text=msg))

        def _do():
            try:
                C.install_email_model(host, _status)
                self.root.after(0, lambda: self._model_status_lbl.config(text="✓ Ready", foreground='green'))
                self.root.after(0, self._pull_btn.grid_remove)
            except Exception as e:
                _status(f"✗ {e}")
                self.root.after(0, lambda: self._pull_btn.config(state='normal'))

        threading.Thread(target=_do, daemon=True).start()

    # ── General tab ───────────────────────────────────
    def _build_general_tab(self):
        f = self.tab_gen

        ttk.Label(f, text="General Settings", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Your Name:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_name = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_name, width=30).grid(row=1, column=1, sticky='ew', pady=4)

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
        ttk.Label(f, text="Removes Coda, its settings, contacts, shortcuts and the email AI model.",
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
                "  •  Your Coda settings and contacts\n"
                "  •  The app launcher, autostart and right-click menu\n"
                "  •  The 'coda' terminal command\n"
                "  •  The coding engine (aider) installed for Coda\n"
                f"  •  The {C.EMAIL_MODEL} email model\n\n"
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

        self.var_email_prov.set(c.get('email_provider', 'Gmail'))
        self.var_email.set(c.get('email', ''))
        self.var_app_pw.set(c.get('app_password', ''))
        self.var_imap.set(c.get('imap_server', 'imap.gmail.com'))
        self.var_smtp.set(c.get('smtp_server', 'smtp.gmail.com'))
        self.var_sync_count.set(str(c.get('email_sync_count', 15)))
        self.var_refresh.set(str(c.get('refresh_minutes', 5)))

        self.var_name.set(c.get('user_name', ''))
        self.var_theme.set(c.get('theme', 'light').capitalize())
        self.var_email_ollama_ip.set(c.get('email_ollama_ip', 'localhost'))
        ai = c.get('email_ai', 'local') if c.get('email_ai') in C.EMAIL_AI else 'local'
        self._email_ai_current = ai
        self.var_email_ai.set(C.EMAIL_AI[ai]['label'])
        self.var_email_ai_model.set(c.get('email_ai_model', ''))
        self.var_email_ai_key.set(c.get('email_ai_key', ''))
        self._show_email_ai(ai)
        self.var_email_on.set(bool(c.get('email_enabled', True)))
        self._on_email_toggle()
        self.root.after(400, self._check_model_status)

    # ── Save ──────────────────────────────────────────
    def _save(self):
        try:
            refresh = int(self.var_refresh.get())
            if refresh < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Auto-refresh must be a positive number.")
            return
        try:
            sync_count = int(self.var_sync_count.get())
            if sync_count < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Emails to sync must be a positive number.")
            return

        self.cfg.update({
            "engine":            self._engine_key(),
            "provider":          self.var_provider.get(),
            "ollama_ip":         self.var_ip.get().strip(),
            "model":             self.var_model.get().strip(),
            "api_key":           self.var_key.get().strip(),
            "email_provider":    self.var_email_prov.get(),
            "email":             self.var_email.get().strip(),
            "app_password":      self.var_app_pw.get().strip(),
            "imap_server":       self.var_imap.get().strip(),
            "smtp_server":       self.var_smtp.get().strip(),
            "user_name":         self.var_name.get().strip(),
            "refresh_minutes":   refresh,
            "email_sync_count":  sync_count,
            "theme":             self.var_theme.get().lower(),
            "email_ollama_ip":   self.var_email_ollama_ip.get().strip() or 'localhost',
            "email_enabled":     bool(self.var_email_on.get()),
            "email_ai":          self._email_ai_key(),
            "email_ai_model":    self.var_email_ai_model.get().strip(),
            "email_ai_key":      self.var_email_ai_key.get().strip(),
        })

        for stale in ('alias', 'learning_mode', 'email_ai_provider', 'custom_url'):
            self.cfg.pop(stale, None)
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
