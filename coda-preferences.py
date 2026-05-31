#!/usr/bin/python3

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

CONFIG_FILE = os.path.expanduser('~/.config/coda/config.json')

PROVIDERS = ['Ollama (local)', 'Claude API', 'OpenAI', 'Groq', 'Custom']
EMAIL_PROVIDERS = ['Gmail', 'Outlook', 'Yahoo', 'Custom']

IMAP_PRESETS = {
    'Gmail':   ('imap.gmail.com', 'smtp.gmail.com'),
    'Outlook': ('outlook.office365.com', 'smtp.office365.com'),
    'Yahoo':   ('imap.mail.yahoo.com', 'smtp.mail.yahoo.com'),
    'Custom':  ('', ''),
}

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

class PreferencesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Coda Preferences")
        self.root.geometry("520x580")
        self.root.resizable(False, False)
        self.root.configure(bg='#1a1a2e')
        self.config = load_config()
        self.build_ui()
        self.load_values()

    def build_ui(self):
        # Title
        tk.Label(self.root, text="Coda Preferences", font=('DejaVu Sans', 16, 'bold'),
                bg='#1a1a2e', fg='#00d4ff').pack(pady=12)

        # Notebook tabs
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#1a1a2e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#0f0f1a', foreground='#aaaaaa',
                        padding=[15, 6], font=('DejaVu Sans', 10))
        style.map('TNotebook.Tab', background=[('selected', '#00d4ff')],
                  foreground=[('selected', 'black')])
        style.configure('TFrame', background='#1a1a2e')

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=4)

        # Tabs
        self.ai_tab = ttk.Frame(self.notebook)
        self.email_tab = ttk.Frame(self.notebook)
        self.general_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.ai_tab, text='🤖 AI Provider')
        self.notebook.add(self.email_tab, text='📧 Email')
        self.notebook.add(self.general_tab, text='⚙ General')

        self.build_ai_tab()
        self.build_email_tab()
        self.build_general_tab()

        # Save button
        tk.Button(self.root, text="💾 Save Preferences", command=self.save,
                 bg='#00d4ff', fg='black', font=('DejaVu Sans', 11, 'bold'),
                 relief='flat', padx=20, pady=8).pack(pady=12)

    def label(self, parent, text):
        tk.Label(parent, text=text, font=('DejaVu Sans', 10),
                bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', padx=20, pady=(10,0))

    def entry(self, parent, show=None):
        e = tk.Entry(parent, bg='#0f0f1a', fg='white', font=('DejaVu Sans', 10),
                    relief='flat', bd=6, insertbackground='white', show=show or '')
        e.pack(fill='x', padx=20, pady=2)
        return e

    def dropdown(self, parent, options, callback=None):
        var = tk.StringVar()
        menu = ttk.Combobox(parent, textvariable=var, values=options,
                           state='readonly', font=('DejaVu Sans', 10))
        menu.pack(fill='x', padx=20, pady=2)
        style = ttk.Style()
        style.configure('TCombobox', fieldbackground='#0f0f1a', background='#0f0f1a',
                        foreground='white', selectbackground='#00d4ff')
        if callback:
            var.trace('w', lambda *a: callback(var.get()))
        return var, menu

    def build_ai_tab(self):
        self.label(self.ai_tab, "Provider:")
        self.provider_var, _ = self.dropdown(self.ai_tab, PROVIDERS, self.on_provider_change)

        self.ollama_frame = tk.Frame(self.ai_tab, bg='#1a1a2e')
        self.ollama_frame.pack(fill='x')
        tk.Label(self.ollama_frame, text="Ollama Server IP:", font=('DejaVu Sans', 10),
                bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', padx=20, pady=(10,0))
        self.ollama_ip = tk.Entry(self.ollama_frame, bg='#0f0f1a', fg='white',
                                   font=('DejaVu Sans', 10), relief='flat', bd=6,
                                   insertbackground='white')
        self.ollama_ip.pack(fill='x', padx=20, pady=2)

        self.apikey_frame = tk.Frame(self.ai_tab, bg='#1a1a2e')
        self.apikey_frame.pack(fill='x')
        tk.Label(self.apikey_frame, text="API Key:", font=('DejaVu Sans', 10),
                bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', padx=20, pady=(10,0))
        self.api_key = tk.Entry(self.apikey_frame, bg='#0f0f1a', fg='white',
                                 font=('DejaVu Sans', 10), relief='flat', bd=6,
                                 insertbackground='white', show='•')
        self.api_key.pack(fill='x', padx=20, pady=2)

        self.label(self.ai_tab, "Model:")
        self.model = self.entry(self.ai_tab)

        self.custom_frame = tk.Frame(self.ai_tab, bg='#1a1a2e')
        self.custom_frame.pack(fill='x')
        tk.Label(self.custom_frame, text="Custom API Base URL:", font=('DejaVu Sans', 10),
                bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', padx=20, pady=(10,0))
        self.custom_url = tk.Entry(self.custom_frame, bg='#0f0f1a', fg='white',
                                    font=('DejaVu Sans', 10), relief='flat', bd=6,
                                    insertbackground='white')
        self.custom_url.pack(fill='x', padx=20, pady=2)

        tk.Label(self.ai_tab, text="e.g. http://localhost:11434 for Ollama, or https://api.anthropic.com",
                font=('DejaVu Sans', 8), bg='#1a1a2e', fg='#555555').pack(anchor='w', padx=20)

    def build_email_tab(self):
        self.label(self.email_tab, "Email Provider:")
        self.email_provider_var, _ = self.dropdown(self.email_tab, EMAIL_PROVIDERS, self.on_email_provider_change)

        self.label(self.email_tab, "Email Address:")
        self.email_address = self.entry(self.email_tab)

        self.label(self.email_tab, "App Password:")
        self.email_password = self.entry(self.email_tab, show='•')

        tk.Label(self.email_tab,
                text="For Gmail: myaccount.google.com → Security → App Passwords",
                font=('DejaVu Sans', 8), bg='#1a1a2e', fg='#555555').pack(anchor='w', padx=20)

        self.label(self.email_tab, "IMAP Server:")
        self.imap_server = self.entry(self.email_tab)

        self.label(self.email_tab, "SMTP Server:")
        self.smtp_server = self.entry(self.email_tab)

    def build_general_tab(self):
        self.label(self.general_tab, "Terminal command name:")
        self.alias_name = self.entry(self.general_tab)
        tk.Label(self.general_tab, text="The command you type in terminal to launch Coda (e.g. coda, coda2)",
                font=('DejaVu Sans', 8), bg='#1a1a2e', fg='#555555').pack(anchor='w', padx=20)

        self.label(self.general_tab, "Email auto-refresh interval (minutes):")
        self.refresh_interval = self.entry(self.general_tab)

        self.label(self.general_tab, "Your name (for email sign-off):")
        self.user_name = self.entry(self.general_tab)

    def on_provider_change(self, value):
        is_ollama = value == 'Ollama (local)'
        is_custom = value == 'Custom'
        needs_key = value in ['Claude API', 'OpenAI', 'Groq', 'Custom']

        if is_ollama:
            self.ollama_frame.pack(fill='x', after=self.ai_tab.winfo_children()[1])
        else:
            self.ollama_frame.pack_forget()

        if needs_key:
            self.apikey_frame.pack(fill='x')
        else:
            self.apikey_frame.pack_forget()

        if is_custom:
            self.custom_frame.pack(fill='x')
        else:
            self.custom_frame.pack_forget()

    def on_email_provider_change(self, value):
        if value in IMAP_PRESETS and value != 'Custom':
            imap, smtp = IMAP_PRESETS[value]
            self.imap_server.delete(0, 'end')
            self.imap_server.insert(0, imap)
            self.smtp_server.delete(0, 'end')
            self.smtp_server.insert(0, smtp)

    def load_values(self):
        c = self.config

        # AI
        provider = c.get('provider', 'Ollama (local)')
        self.provider_var.set(provider)
        self.on_provider_change(provider)
        self.ollama_ip.insert(0, c.get('ollama_ip', ''))
        self.api_key.insert(0, c.get('api_key', ''))
        self.model.insert(0, c.get('model', ''))
        self.custom_url.insert(0, c.get('custom_url', ''))

        # Email
        ep = c.get('email_provider', 'Gmail')
        self.email_provider_var.set(ep)
        self.email_address.insert(0, c.get('email', ''))
        self.email_password.insert(0, c.get('app_password', ''))
        self.imap_server.insert(0, c.get('imap_server', 'imap.gmail.com'))
        self.smtp_server.insert(0, c.get('smtp_server', 'smtp.gmail.com'))

        # General
        self.alias_name.insert(0, c.get('alias', 'coda'))
        self.refresh_interval.insert(0, str(c.get('refresh_minutes', 5)))
        self.user_name.insert(0, c.get('user_name', ''))

    def save(self):
        config = {
            'provider': self.provider_var.get(),
            'ollama_ip': self.ollama_ip.get().strip(),
            'api_key': self.api_key.get().strip(),
            'model': self.model.get().strip(),
            'custom_url': self.custom_url.get().strip(),
            'email_provider': self.email_provider_var.get(),
            'email': self.email_address.get().strip(),
            'app_password': self.email_password.get().strip(),
            'imap_server': self.imap_server.get().strip(),
            'smtp_server': self.smtp_server.get().strip(),
            'alias': self.alias_name.get().strip(),
            'refresh_minutes': int(self.refresh_interval.get().strip() or 5),
            'user_name': self.user_name.get().strip(),
        }
        save_config(config)

        # Update ~/.bashrc alias
        alias_line = f"alias {config['alias']}='source ~/aider-env/bin/activate && "
        if config['provider'] == 'Ollama (local)':
            alias_line += f"OLLAMA_API_BASE=http://{config['ollama_ip']}:11434 aider --model ollama/{config['model']}'"
        elif config['provider'] == 'Claude API':
            alias_line += f"ANTHROPIC_API_KEY={config['api_key']} aider --model {config['model']}'"
        elif config['provider'] == 'OpenAI':
            alias_line += f"OPENAI_API_KEY={config['api_key']} aider --model {config['model']}'"
        elif config['provider'] == 'Groq':
            alias_line += f"GROQ_API_KEY={config['api_key']} aider --model groq/{config['model']}'"
        else:
            alias_line += f"OPENAI_API_BASE={config['custom_url']} aider --model {config['model']}'"

        bashrc = os.path.expanduser('~/.bashrc')
        with open(bashrc) as f:
            lines = f.readlines()
        lines = [l for l in lines if not l.strip().startswith('alias coda')]
        lines.append(f"\n# Coda AI assistant\n{alias_line}\n")
        with open(bashrc, 'w') as f:
            f.writelines(lines)

        # Update email config
        email_conf = os.path.expanduser('~/.config/coda/email.conf')
        with open(email_conf, 'w') as f:
            f.write(f"EMAIL={config['email']}\n")
            f.write(f"APP_PASSWORD={config['app_password']}\n")
            f.write(f"IMAP_SERVER={config['imap_server']}\n")
            f.write(f"SMTP_SERVER={config['smtp_server']}\n")
            f.write(f"OLLAMA_IP={config['ollama_ip']}\n")
            f.write(f"MODEL={config['model']}\n")

        messagebox.showinfo("Saved!", "Preferences saved!\nRestart Coda for all changes to take effect.")

if __name__ == '__main__':
    root = tk.Tk()
    app = PreferencesApp(root)
    root.mainloop()
