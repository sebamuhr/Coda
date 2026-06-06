#!/usr/bin/python3
import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import shutil
import subprocess
import threading
import urllib.request

CONFIG_FILE = os.path.expanduser('~/.config/coda/config.json')
EMAIL_CONF  = os.path.expanduser('~/.config/coda/email.conf')

PROVIDERS = ["Ollama (local)", "Gemini", "OpenAI", "Claude"]

PROVIDER_MODELS = {
    "Ollama (local)": ["(enter your model name)"],
    "Gemini":         ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "OpenAI":         ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "Claude":         ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
}

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
        "user_name": "",
        "email_ai_provider": "Ollama (local)",
        "email_ai_key": "",
        "email_sync_count": 15,
        "theme": "light",
        "learning_mode": "silent",
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

def write_email_conf(cfg):
    lines = [
        f"EMAIL={cfg.get('email','')}",
        f"APP_PASSWORD={cfg.get('app_password','')}",
        f"IMAP_SERVER={cfg.get('imap_server','')}",
        f"SMTP_SERVER={cfg.get('smtp_server','')}",
        f"PROVIDER={cfg.get('email_provider','')}",
        f"OLLAMA_IP={cfg.get('ollama_ip','')}",
        f"MODEL={cfg.get('model','')}",
        f"SYNC_COUNT={cfg.get('email_sync_count', 15)}",
        f"THEME={cfg.get('theme', 'light')}",
        f"LEARNING_MODE={cfg.get('learning_mode', 'silent')}",
    ]
    os.makedirs(os.path.dirname(EMAIL_CONF), exist_ok=True)
    with open(EMAIL_CONF, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    os.chmod(EMAIL_CONF, 0o600)

def update_bashrc_alias(alias, cfg):
    bashrc = os.path.expanduser('~/.bashrc')
    provider = cfg.get('provider', 'Ollama (local)')
    model = cfg.get('model', '')
    api_key = cfg.get('api_key', '')
    ollama_ip = cfg.get('ollama_ip', '')

    if provider == "Ollama (local)":
        base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
        new_alias = (
            f"alias {alias}='source ~/aider-env/bin/activate && "
            f"OLLAMA_API_BASE={base_url} aider --model ollama/{model}'"
        )
    elif provider == "Gemini":
        default_model = model or 'gemini-1.5-pro'
        new_alias = (
            f"alias {alias}='source ~/aider-env/bin/activate && "
            f"GEMINI_API_KEY={api_key} aider --model gemini/{default_model}'"
        )
    elif provider == "OpenAI":
        default_model = model or 'gpt-4o'
        new_alias = (
            f"alias {alias}='source ~/aider-env/bin/activate && "
            f"OPENAI_API_KEY={api_key} aider --model {default_model}'"
        )
    elif provider == "Claude":
        default_model = model or 'claude-opus-4-5'
        new_alias = (
            f"alias {alias}='source ~/aider-env/bin/activate && "
            f"ANTHROPIC_API_KEY={api_key} aider --model {default_model}'"
        )
    else:
        return

    try:
        with open(bashrc, 'r') as f:
            lines = f.readlines()
        lines = [l for l in lines if not l.strip().startswith(f"alias {alias}=")]
        lines.append(new_alias + '\n')
        with open(bashrc, 'w') as f:
            f.writelines(lines)
    except Exception:
        pass

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

        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_ai    = ttk.Frame(nb, padding=16)
        self.tab_email = ttk.Frame(nb, padding=16)
        self.tab_gen   = ttk.Frame(nb, padding=16)

        nb.add(self.tab_ai,    text='  Call Coda  ')
        nb.add(self.tab_email, text='  Email  ')
        nb.add(self.tab_gen,   text='  General  ')

        self._build_ai_tab()
        self._build_email_tab()
        self._build_general_tab()

        # Save button
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill='x', padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text='Save', command=self._save, width=14).pack(side='right')
        ttk.Button(btn_frame, text='Cancel', command=self.root.destroy, width=10).pack(side='right', padx=6)

    # ── AI Provider tab ──────────────────────────────
    def _build_ai_tab(self):
        f = self.tab_ai

        ttk.Label(f, text="AI Provider", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Provider:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_provider = tk.StringVar()
        self.cb_provider = ttk.Combobox(f, textvariable=self.var_provider, values=PROVIDERS, state='readonly', width=28)
        self.cb_provider.grid(row=1, column=1, sticky='ew', pady=4)
        self.cb_provider.bind('<<ComboboxSelected>>', self._on_provider_change)

        # Ollama-only: server IP
        self.lbl_ip = ttk.Label(f, text="Ollama Server IP:")
        self.lbl_ip.grid(row=2, column=0, sticky='w', pady=4)
        self.var_ip = tk.StringVar()
        self.ent_ip = ttk.Entry(f, textvariable=self.var_ip, width=30)
        self.ent_ip.grid(row=2, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="Model:").grid(row=3, column=0, sticky='w', pady=4)
        self.var_model = tk.StringVar()
        self.cb_model = ttk.Combobox(f, textvariable=self.var_model, width=28)
        self.cb_model.grid(row=3, column=1, sticky='ew', pady=4)

        # API key (cloud providers only)
        self.lbl_key = ttk.Label(f, text="API Key:")
        self.lbl_key.grid(row=4, column=0, sticky='w', pady=4)
        self.var_key = tk.StringVar()
        self.ent_key = ttk.Entry(f, textvariable=self.var_key, show='*', width=30)
        self.ent_key.grid(row=4, column=1, sticky='ew', pady=4)

        self.lbl_key_help = ttk.Label(f, text="", foreground='gray', font=('', 9))
        self.lbl_key_help.grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 6))

        f.columnconfigure(1, weight=1)

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

        ttk.Label(f, text="Email Account", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Email Provider:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_email_prov = tk.StringVar()
        self.cb_email_prov = ttk.Combobox(f, textvariable=self.var_email_prov, values=EMAIL_PROVIDERS, state='readonly', width=28)
        self.cb_email_prov.grid(row=1, column=1, sticky='ew', pady=4)
        self.cb_email_prov.bind('<<ComboboxSelected>>', self._on_email_provider_change)

        ttk.Label(f, text="Email Address:").grid(row=2, column=0, sticky='w', pady=4)
        self.var_email = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_email, width=30).grid(row=2, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="App Password:").grid(row=3, column=0, sticky='w', pady=4)
        self.var_app_pw = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_app_pw, show='*', width=30).grid(row=3, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="⚠ Not your Gmail password — create one at:\n"
                          "myaccount.google.com → Security → 2-Step Verification → App Passwords",
                  foreground='gray', font=('', 8)).grid(
                      row=4, column=0, columnspan=2, sticky='w', pady=(0, 6))

        ttk.Label(f, text="IMAP Server:").grid(row=5, column=0, sticky='w', pady=4)
        self.var_imap = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_imap, width=30).grid(row=5, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="SMTP Server:").grid(row=6, column=0, sticky='w', pady=4)
        self.var_smtp = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_smtp, width=30).grid(row=6, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="Emails to sync:").grid(row=7, column=0, sticky='w', pady=4)
        self.var_sync_count = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_sync_count, width=8).grid(row=7, column=1, sticky='w', pady=4)

        ttk.Label(f, text="Auto-refresh (minutes):").grid(row=8, column=0, sticky='w', pady=4)
        self.var_refresh = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_refresh, width=8).grid(row=8, column=1, sticky='w', pady=4)

        ttk.Separator(f).grid(row=9, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(f, text="Email AI", font=('', 11, 'bold')).grid(row=10, column=0, columnspan=2, sticky='w', pady=(0,6))
        ttk.Label(f, text="Model:").grid(row=11, column=0, sticky='w', pady=4)
        ttk.Label(f, text="coda2.0:3b (local)", font=('', 10, 'bold')).grid(row=11, column=1, sticky='w', pady=4)

        ttk.Label(f, text="Status:").grid(row=12, column=0, sticky='w', pady=4)
        self._model_status_lbl = ttk.Label(f, text="Checking...", foreground='gray')
        self._model_status_lbl.grid(row=12, column=1, sticky='w', pady=4)

        self._pull_btn = ttk.Button(f, text='⬇  Pull Model',
                                     command=self._pull_model, width=16)
        self._pull_btn.grid(row=13, column=1, sticky='w', pady=(0, 4))
        self._pull_btn.grid_remove()

        self._pull_progress = ttk.Label(f, text='', foreground='gray', font=('', 8))
        self._pull_progress.grid(row=14, column=0, columnspan=2, sticky='w')
        self._pull_progress.grid_remove()

        ttk.Label(f, text="The email assistant always runs locally for privacy.",
                  foreground='gray', font=('', 8)).grid(row=15, column=0, columnspan=2, sticky='w')

        ttk.Separator(f).grid(row=16, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(f, text="Learning", font=('', 11, 'bold')).grid(row=17, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Label(f, text="When you edit Coda's reply before sending:").grid(row=18, column=0, columnspan=2, sticky='w')

        ttk.Label(f, text="Learning mode:").grid(row=19, column=0, sticky='w', pady=4)
        self.var_learning = tk.StringVar()
        ttk.Combobox(f, textvariable=self.var_learning, values=['Silent', 'Approval'],
                     state='readonly', width=14).grid(row=19, column=1, sticky='w', pady=4)
        ttk.Label(f, text="Silent: saves corrections automatically\n"
                          "Approval: asks you before saving each correction",
                  foreground='gray', font=('', 8)).grid(row=20, column=0, columnspan=2, sticky='w')

        f.columnconfigure(1, weight=1)

    def _ollama_base_url(self):
        ip = self.var_ip.get().strip()
        ip = (ip or 'localhost').replace('http://', '').replace('https://', '').strip('/') or 'localhost'
        return f"http://{ip}:11434"

    def _check_model_status(self):
        self._model_status_lbl.config(text="Checking…", foreground='gray')
        self._pull_btn.grid_remove()

        def _check():
            try:
                url = self._ollama_base_url() + '/api/tags'
                with urllib.request.urlopen(url, timeout=5) as r:
                    data = json.loads(r.read())
                found = any('coda2.0:3b' in m.get('name', '')
                            for m in data.get('models', []))
            except Exception:
                found = False
            if found:
                self.root.after(0, lambda: self._model_status_lbl.config(
                    text="✓ Ready", foreground='green'))
                self.root.after(0, self._pull_btn.grid_remove)
            else:
                self.root.after(0, lambda: self._model_status_lbl.config(
                    text="✗ Not installed", foreground='red'))
                self.root.after(0, self._pull_btn.grid)

        threading.Thread(target=_check, daemon=True).start()

    def _pull_model(self):
        self._pull_btn.config(state='disabled')
        self._pull_progress.grid()

        def _status(msg):
            self.root.after(0, lambda: self._pull_progress.config(text=msg))

        def _do():
            base = self._ollama_base_url()
            try:
                _status("Downloading qwen2.5:3b — this may take a few minutes…")
                data = json.dumps({'name': 'qwen2.5:3b', 'stream': False}).encode()
                req  = urllib.request.Request(f"{base}/api/pull", data=data,
                                              headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=600)

                _status("Creating coda2.0:3b…")
                modelfile = (
                    'FROM qwen2.5:3b\n'
                    'SYSTEM "You write emails on behalf of the user. '
                    'Write naturally and concisely in their voice. '
                    'Do not use robotic phrases or unnecessary pleasantries."'
                )
                data = json.dumps({'name': 'coda2.0:3b',
                                   'modelfile': modelfile,
                                   'stream': False}).encode()
                req  = urllib.request.Request(f"{base}/api/create", data=data,
                                              headers={'Content-Type': 'application/json'})
                urllib.request.urlopen(req, timeout=180)

                _status("Removing qwen2.5:3b…")
                data = json.dumps({'name': 'qwen2.5:3b'}).encode()
                req  = urllib.request.Request(f"{base}/api/delete", data=data,
                                              headers={'Content-Type': 'application/json'},
                                              method='DELETE')
                try:
                    urllib.request.urlopen(req, timeout=30)
                except Exception:
                    pass

                _status("✓ coda2.0:3b installed!")
                self.root.after(0, lambda: self._model_status_lbl.config(
                    text="✓ Ready", foreground='green'))
                self.root.after(0, self._pull_btn.grid_remove)

            except Exception as e:
                _status(f"✗ Error: {e}")
                self.root.after(0, lambda: self._pull_btn.config(state='normal'))

        threading.Thread(target=_do, daemon=True).start()

    def _on_email_provider_change(self, event=None):
        prov = self.var_email_prov.get()
        imap, smtp = EMAIL_IMAP.get(prov, ("", ""))
        self.var_imap.set(imap)
        self.var_smtp.set(smtp)

    # ── General tab ───────────────────────────────────
    def _build_general_tab(self):
        f = self.tab_gen

        ttk.Label(f, text="General Settings", font=('', 11, 'bold')).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0,10))

        ttk.Label(f, text="Your Name:").grid(row=1, column=0, sticky='w', pady=4)
        self.var_name = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_name, width=30).grid(row=1, column=1, sticky='ew', pady=4)

        ttk.Label(f, text="Terminal alias:").grid(row=2, column=0, sticky='w', pady=4)
        self.var_alias = tk.StringVar()
        ttk.Entry(f, textvariable=self.var_alias, width=30, state='readonly').grid(row=2, column=1, sticky='ew', pady=4)
        ttk.Label(f, text="Fixed — type 'coda' in terminal to launch", foreground='gray', font=('', 9)).grid(
            row=3, column=0, columnspan=2, sticky='w')

        ttk.Label(f, text="Theme:").grid(row=4, column=0, sticky='w', pady=10)
        self.var_theme = tk.StringVar()
        ttk.Combobox(f, textvariable=self.var_theme, values=['Light', 'Dark', 'Auto'],
                     state='readonly', width=14).grid(row=4, column=1, sticky='w', pady=10)
        ttk.Label(f, text="Restart Coda to apply a theme change", foreground='gray', font=('', 9)).grid(
            row=5, column=0, columnspan=2, sticky='w')

        ttk.Separator(f).grid(row=6, column=0, columnspan=2, sticky='ew', pady=16)

        ttk.Label(f, text="Uninstall", font=('', 11, 'bold')).grid(row=7, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Button(f, text='🗑  Uninstall Coda', command=self._uninstall,
                   width=20).grid(row=8, column=0, sticky='w')
        ttk.Label(f, text="Removes all Coda files, config, contacts,\nlearned data, shortcuts and the AI model.",
                  foreground='gray', font=('', 8)).grid(row=9, column=0, columnspan=2, sticky='w', pady=(4, 0))

        f.columnconfigure(1, weight=1)

    def _uninstall(self):
        if not messagebox.askyesno(
                "Uninstall Coda",
                "This will permanently remove:\n\n"
                "  •  All configuration and contacts\n"
                "  •  Learned email preferences\n"
                "  •  Desktop shortcuts and autostart\n"
                "  •  The Coda app files\n"
                "  •  The coda2.0:3b AI model\n\n"
                "This cannot be undone. Are you sure?",
                icon='warning'):
            return
        if not messagebox.askyesno(
                "Really uninstall?",
                "Last chance — remove Coda completely?",
                icon='warning'):
            return

        # Remove Ollama model
        try:
            cfg = load_config()
            ip = (cfg.get('ollama_ip', '') or 'localhost').replace('http://', '').replace('https://', '').strip('/') or 'localhost'
            subprocess.run(
                ['curl', '-s', '-X', 'DELETE',
                 f'http://{ip}:11434/api/delete',
                 '-H', 'Content-Type: application/json',
                 '-d', '{"name":"coda2.0:3b"}'],
                timeout=10, capture_output=True)
        except Exception:
            pass

        # Remove config directory
        shutil.rmtree(os.path.expanduser('~/.config/coda'), ignore_errors=True)

        # Remove desktop / icon / autostart files
        for path in [
            '~/.config/autostart/coda.desktop',
            '~/.local/share/applications/coda.desktop',
            '~/Desktop/coda.desktop',
            '~/.local/share/icons/coda.svg',
        ]:
            try:
                os.remove(os.path.expanduser(path))
            except Exception:
                pass

        # Remove .bashrc alias lines
        try:
            bashrc = os.path.expanduser('~/.bashrc')
            with open(bashrc, 'r') as f:
                lines = f.readlines()
            lines = [l for l in lines
                     if '# Coda' not in l and 'alias coda' not in l
                     and 'coda-tray' not in l]
            with open(bashrc, 'w') as f:
                f.writelines(lines)
        except Exception:
            pass

        # Remove Nautilus extension
        try:
            subprocess.run(
                ['sudo', 'rm', '-f',
                 '/usr/share/nautilus-python/extensions/coda_extension.py'],
                timeout=10, capture_output=True)
        except Exception:
            pass

        # Schedule app directory deletion + kill tray after this process exits
        coda_dir = os.path.dirname(os.path.abspath(__file__))
        cleanup = f'sleep 2 && rm -rf "{coda_dir}" && pkill -f coda-tray.py'
        subprocess.Popen(['bash', '-c', cleanup])

        messagebox.showinfo("Uninstalled", "Coda has been uninstalled.\nThe app will close now.")
        self.root.destroy()

    # ── Load values ───────────────────────────────────
    def _load_values(self):
        c = self.cfg
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
        self.var_alias.set('coda')
        self.var_theme.set(c.get('theme', 'light').capitalize())
        self.var_learning.set(c.get('learning_mode', 'silent').capitalize())
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
            "alias":             "coda",
            "refresh_minutes":   refresh,
            "email_sync_count":  sync_count,
            "theme":             self.var_theme.get().lower(),
            "learning_mode":     self.var_learning.get().lower(),
        })

        save_config(self.cfg)
        write_email_conf(self.cfg)
        update_bashrc_alias(self.cfg['alias'], self.cfg)

        messagebox.showinfo("Saved", "Preferences saved!\n\nRestart Coda from the taskbar to apply provider changes.")
        self.root.destroy()


def main():
    root = tk.Tk()
    app = PreferencesApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
