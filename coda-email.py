#!/usr/bin/python3

import imaplib
import smtplib
import email
import email.utils
import html as _html
import requests
import re
import json
import os
import signal
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

# --- Config (read fresh on every call so Preferences changes take effect immediately) ---
def _cfg():
    c = {}
    try:
        with open(os.path.expanduser('~/.config/coda/email.conf')) as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    c[k] = v
    except Exception:
        pass
    return c

PREFS_FILE = os.path.expanduser('~/.config/coda/window.json')

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
AUTO_REFRESH_MINUTES = 5

# --- Window prefs ---
def save_prefs(geometry):
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    with open(PREFS_FILE, 'w') as f:
        json.dump({'geometry': geometry}, f)

def load_prefs():
    try:
        with open(PREFS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

# --- Email utilities ---
def decode_str(s):
    if s is None:
        return ''
    result = ''
    for part, enc in decode_header(s):
        if isinstance(part, bytes):
            result += part.decode(enc or 'utf-8', errors='replace')
        else:
            result += part
    return result

def strip_html(h):
    h = h.replace('\r\n', '\n').replace('\r', '\n')
    h = re.sub(r'<head\b[^>]*>.*?</head>', '', h, flags=re.DOTALL | re.IGNORECASE)
    h = re.sub(r'<!--.*?-->', '', h, flags=re.DOTALL)
    h = re.sub(r'<(style|script)\b[^>]*>.*?</(style|script)>', '', h, flags=re.DOTALL | re.IGNORECASE)
    h = re.sub(r'(src|href)=["\']data:[^"\']*["\']', '', h, flags=re.IGNORECASE)
    h = re.sub(r'<(br|p|div|tr|li|td|th|h[1-6]|blockquote|pre|ul|ol)\b[^>]*>', '\n', h, flags=re.IGNORECASE)
    h = re.sub(r'<[^>]*>', '', h)
    h = _html.unescape(h)
    h = re.sub(r'[ \t\xa0]+', ' ', h)
    h = re.sub(r'\n[ \t]*', '\n', h)
    return re.sub(r'\n{3,}', '\n\n', h).strip()

def get_body(msg):
    plain = html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain' and not plain:
                try:
                    plain = part.get_payload(decode=True).decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
                except Exception:
                    pass
            elif ct == 'text/html' and not html:
                try:
                    html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except Exception:
                    pass
    else:
        try:
            raw = msg.get_payload(decode=True).decode('utf-8', errors='replace').replace('\r\n', '\n').replace('\r', '\n')
            if msg.get_content_type() == 'text/html':
                html = raw
            else:
                plain = raw
        except Exception:
            pass
    if plain:
        return plain[:3000]
    if html:
        return strip_html(html)[:3000]
    return ''

def fetch_emails(folder='INBOX', criteria='UNSEEN'):
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    mail.select(folder, readonly=True)
    _, data = mail.search(None, criteria)
    count = int(cfg.get('SYNC_COUNT', '15'))
    ids = data[0].split()[-count:]
    result = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(BODY.PEEK[])')
        msg = email.message_from_bytes(msg_data[0][1])
        result.append({
            'id': eid,
            'from':       decode_str(msg['From']),
            'to':         decode_str(msg['To']),
            'subject':    decode_str(msg['Subject']),
            'date':       decode_str(msg['Date']),
            'body':       get_body(msg),
            'message_id': msg.get('Message-ID', ''),
            'references': msg.get('References', ''),
        })
    mail.logout()
    return result

def fetch_drafts():
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    mail.select('"[Gmail]/Drafts"', readonly=True)
    _, data = mail.search(None, 'ALL')
    count = int(cfg.get('SYNC_COUNT', '15'))
    ids = data[0].split()[-count:]
    result = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(BODY.PEEK[])')
        msg = email.message_from_bytes(msg_data[0][1])
        result.append({
            'id': eid,
            'from':       decode_str(msg['From']),
            'to':         decode_str(msg['To']),
            'subject':    decode_str(msg['Subject']),
            'date':       decode_str(msg['Date']),
            'body':       get_body(msg),
            'message_id': msg.get('Message-ID', ''),
            'references': msg.get('References', ''),
        })
    mail.logout()
    return result

def build_msg(to, subject, body, selected_email=None):
    msg = MIMEMultipart('alternative')
    msg['From']    = _cfg().get('EMAIL', '')
    msg['To']      = to
    msg['Subject'] = ('Re: ' + subject) if selected_email and not subject.startswith('Re:') else subject
    msg['Date']    = email.utils.formatdate(localtime=True)
    if selected_email and selected_email.get('message_id'):
        msg['In-Reply-To'] = selected_email['message_id']
        refs = selected_email.get('references', '')
        msg['References'] = (refs + ' ' + selected_email['message_id']).strip()
    msg.attach(MIMEText(body, 'plain'))
    return msg

def save_draft(to, subject, body, selected_email=None):
    cfg = _cfg()
    msg = build_msg(to, subject, body, selected_email)
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    mail.append('"[Gmail]/Drafts"', '', None, msg.as_bytes())
    mail.logout()

def send_email(to, subject, body, selected_email=None):
    cfg = _cfg()
    msg = build_msg(to, subject, body, selected_email)
    with smtplib.SMTP_SSL(cfg.get('SMTP_SERVER', 'smtp.gmail.com'), 465) as smtp:
        smtp.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
        smtp.sendmail(cfg.get('EMAIL', ''), to, msg.as_bytes())

def ask_coda(context, instruction, mode='reply'):
    if mode == 'new':
        prompt = (
            "You are an email assistant. Write a professional email based on the instruction below.\n\n"
            f"INSTRUCTION:\n{instruction}\n\n"
            "Write only the email body. No subject line. Sign off as Sebastian."
        )
    else:
        prompt = (
            "You are an email assistant. Based on the email conversation below, write a professional reply.\n\n"
            f"EMAIL CONTEXT:\n{context}\n\n"
            f"USER INSTRUCTION:\n{instruction}\n\n"
            "Write only the email body. No subject line. Sign off as Sebastian."
        )
    try:
        cfg = _cfg()
        ollama_ip = cfg.get('OLLAMA_IP', 'localhost').replace('https://', '').replace('http://', '').strip('/')
        resp = requests.post(
            f"http://{ollama_ip}:11434/api/generate",
            json={'model': cfg.get('MODEL', 'coda:2.0'), 'prompt': prompt, 'stream': False},
            timeout=120,
        )
        return resp.json()['response']
    except Exception as e:
        return f"Error calling Coda: {e}"


# ─────────────────────────────────────────────────────────────────
class EmailApp:

    TAB_KEYS = ('unread', 'read', 'drafts')

    def __init__(self, root):
        self.root = root
        self.root.title("Coda — Email Agent")
        self.root.resizable(True, True)

        prefs = load_prefs()
        self.root.geometry(prefs.get('geometry', '920x760'))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # SIGUSR1 from the tray means "show yourself"
        signal.signal(signal.SIGUSR1,
                      lambda s, f: self.root.after(0, self._show_window))

        apply_theme(root, _cfg().get('THEME', 'light'))

        self.cache    = {k: None for k in self.TAB_KEYS}
        self.selected = {k: None for k in self.TAB_KEYS}
        self.current_tab_key = 'unread'

        self._build_ui()
        self.load_tab('unread')
        self.start_auto_refresh()

    # ── scroll routing ─────────────────────────────────────────────

    def _on_scroll(self, event, direction):
        w = event.widget
        # Tk class-binding already scrolled the widget before bind_all fires.
        # If the widget still has room in this direction it absorbed the scroll —
        # don't also move the outer canvas.  Only fall through when at the limit.
        if isinstance(w, (tk.Listbox, tk.Text)):
            first, last = w.yview()
            if direction < 0 and first > 0:
                return
            if direction > 0 and last < 1:
                return
        self._canvas.yview_scroll(direction, 'units')

    # ── lifecycle ──────────────────────────────────────────────────

    def on_close(self):
        save_prefs(self.root.geometry())
        self.root.withdraw()   # hide, stay alive in background

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def start_auto_refresh(self):
        def _tick():
            self.refresh_current_tab()
            self.root.after(AUTO_REFRESH_MINUTES * 60_000, _tick)
        self.root.after(AUTO_REFRESH_MINUTES * 60_000, _tick)

    def refresh_current_tab(self):
        if self.current_tab_key in self.TAB_KEYS:
            self.cache[self.current_tab_key] = None
            self.load_tab(self.current_tab_key)

    # ── UI build ───────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = ttk.Frame(self.root, padding=(10, 8, 10, 6))
        hdr.pack(fill='x')
        ttk.Label(hdr, text="Coda — Email Agent", font=('', 13, 'bold')).pack(side='left')
        self.status_label = ttk.Label(hdr, text="", font=('', 9), foreground='gray')
        self.status_label.pack(side='right', padx=8)
        ttk.Button(hdr, text="↺  Refresh", command=self.force_refresh, width=11).pack(side='right')

        ttk.Separator(self.root).pack(fill='x')

        # Global scrollable area
        outer = ttk.Frame(self.root)
        outer.pack(fill='both', expand=True)

        self._global_vsb = ttk.Scrollbar(outer, orient='vertical')
        self._global_vsb.pack(side='right', fill='y')

        self._canvas = tk.Canvas(outer, yscrollcommand=self._global_vsb.set,
                                  highlightthickness=0)
        self._canvas.pack(side='left', fill='both', expand=True)
        self._global_vsb.config(command=self._canvas.yview)

        inner = ttk.Frame(self._canvas)
        self._canvas_win = self._canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_canvas_resize(e):
            self._canvas.itemconfig(self._canvas_win,
                                    width=e.width,
                                    height=max(e.height, inner.winfo_reqheight()))
            self._canvas.configure(scrollregion=self._canvas.bbox('all'))

        self._canvas.bind('<Configure>', _on_canvas_resize)
        inner.bind('<Configure>', lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox('all')))

        self._canvas.bind_all('<Button-4>', lambda e: self._on_scroll(e, -1))
        self._canvas.bind_all('<Button-5>', lambda e: self._on_scroll(e,  1))

        # Notebook — same widget as preferences
        self.nb = ttk.Notebook(inner)
        self.nb.pack(fill='both', expand=True, padx=8, pady=(6, 8))

        self._widgets = {}
        for key, label in [('unread', '📬  Unread'),
                            ('read',   '📖  Read'),
                            ('drafts', '📝  Drafts')]:
            frame = ttk.Frame(self.nb, padding=4)
            self.nb.add(frame, text=f'  {label}  ')
            self._widgets[key] = self._make_email_panel(frame, key)

        new_frame = ttk.Frame(self.nb, padding=4)
        self.nb.add(new_frame, text='  ✉  New Email  ')
        self._make_new_email_panel(new_frame)

        self.nb.bind('<<NotebookTabChanged>>', self._on_tab_change)

    def _make_email_panel(self, parent, key):
        """Resizable split view: list / preview / instruction / buttons / reply."""
        paned = tk.PanedWindow(parent, orient='vertical',
                               sashwidth=5, sashrelief='raised')
        paned.pack(fill='both', expand=True)

        # Email list
        lf1 = ttk.LabelFrame(paned, text="Emails", padding=4)
        paned.add(lf1, minsize=70)
        vsb1 = ttk.Scrollbar(lf1)
        vsb1.pack(side='right', fill='y')
        lb = tk.Listbox(lf1, yscrollcommand=vsb1.set, selectmode='single',
                        font=('', 9), relief='flat', borderwidth=1,
                        activestyle='dotbox', exportselection=False)
        lb.pack(fill='both', expand=True)
        vsb1.config(command=lb.yview)
        lb.bind('<<ListboxSelect>>', lambda e, k=key: self._on_select(e, k))

        # Email preview
        lf2 = ttk.LabelFrame(paned, text="Email content", padding=4)
        paned.add(lf2, minsize=70)
        preview = scrolledtext.ScrolledText(lf2, font=('', 9), wrap='word',
                                             relief='flat', borderwidth=1)
        preview.pack(fill='both', expand=True)

        # Instruction
        lf3 = ttk.LabelFrame(paned, text="What do you want to say?", padding=4)
        paned.add(lf3, minsize=70)
        instruction = scrolledtext.ScrolledText(lf3, font=('', 10), wrap='word',
                                                 relief='flat', borderwidth=1, height=4)
        instruction.pack(fill='both', expand=True)

        # Bottom container — one pane holding both buttons (fixed) and reply area (resizable)
        bottom = ttk.Frame(paned)
        paned.add(bottom, minsize=110)

        btn_frm = ttk.Frame(bottom, padding=(4, 6))
        btn_frm.pack(fill='x')
        ttk.Button(btn_frm, text="✍  Write Reply",
                   command=lambda k=key: self._write_reply(k),
                   width=16).pack(side='left', padx=4)
        ttk.Button(btn_frm, text="💾  Save to Drafts",
                   command=lambda k=key: self._save_draft_reply(k),
                   width=18).pack(side='left', padx=4)
        ttk.Button(btn_frm, text="🚀  Send Now",
                   command=lambda k=key: self._send_reply(k),
                   width=14).pack(side='left', padx=4)

        lf4 = ttk.LabelFrame(bottom, text="Coda's reply", padding=4)
        lf4.pack(fill='both', expand=True)
        reply_area = scrolledtext.ScrolledText(lf4, font=('', 9), wrap='word',
                                                relief='flat', borderwidth=1)
        reply_area.pack(fill='both', expand=True)

        return {'listbox': lb, 'preview': preview,
                'instruction': instruction, 'reply': reply_area}

    def _make_new_email_panel(self, parent):
        # To / Subject — fixed, not resizable
        fixed = ttk.Frame(parent, padding=(0, 4))
        fixed.pack(fill='x')
        ttk.Label(fixed, text="To:").grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        self.new_to = ttk.Entry(fixed, font=('', 10))
        self.new_to.grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(fixed, text="Subject:").grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        self.new_subject = ttk.Entry(fixed, font=('', 10))
        self.new_subject.grid(row=1, column=1, sticky='ew', pady=4)
        fixed.columnconfigure(1, weight=1)

        ttk.Separator(parent).pack(fill='x', pady=4)

        # Resizable panels
        paned = tk.PanedWindow(parent, orient='vertical',
                               sashwidth=5, sashrelief='raised')
        paned.pack(fill='both', expand=True)

        lf1 = ttk.LabelFrame(paned, text="What do you want to say?", padding=4)
        paned.add(lf1, minsize=70)
        self.new_instruction = scrolledtext.ScrolledText(lf1, font=('', 10), wrap='word',
                                                          relief='flat', borderwidth=1, height=4)
        self.new_instruction.pack(fill='both', expand=True)

        # Bottom container — buttons fixed, reply area resizable
        bottom = ttk.Frame(paned)
        paned.add(bottom, minsize=110)

        btn_frm = ttk.Frame(bottom, padding=(4, 6))
        btn_frm.pack(fill='x')
        ttk.Button(btn_frm, text="✍  Write Email",
                   command=self._write_new, width=16).pack(side='left', padx=4)
        ttk.Button(btn_frm, text="💾  Save to Drafts",
                   command=self._save_new_draft, width=18).pack(side='left', padx=4)
        ttk.Button(btn_frm, text="🚀  Send Now",
                   command=self._send_new, width=14).pack(side='left', padx=4)

        lf2 = ttk.LabelFrame(bottom, text="Coda's email", padding=4)
        lf2.pack(fill='both', expand=True)
        self.new_reply_area = scrolledtext.ScrolledText(lf2, font=('', 9), wrap='word',
                                                         relief='flat', borderwidth=1)
        self.new_reply_area.pack(fill='both', expand=True)

    # ── tab switching ──────────────────────────────────────────────

    def _on_tab_change(self, event):
        idx  = self.nb.index(self.nb.select())
        keys = list(self.TAB_KEYS) + ['new']
        self.current_tab_key = keys[idx]
        if self.current_tab_key in self.TAB_KEYS:
            self.load_tab(self.current_tab_key)

    # ── loading ────────────────────────────────────────────────────

    def set_status(self, msg):
        self.status_label.config(text=msg)
        self.root.update_idletasks()

    def force_refresh(self):
        if self.current_tab_key in self.TAB_KEYS:
            self.cache[self.current_tab_key] = None
            self.load_tab(self.current_tab_key)

    def load_tab(self, key):
        if key not in self.TAB_KEYS:
            return
        if self.cache[key] is not None:
            self._render_emails(key, self.cache[key])
            self.set_status("Cached — click ↺ Refresh to reload")
            return

        lb = self._widgets[key]['listbox']
        lb.delete(0, 'end')
        lb.insert('end', '  Loading…')
        self.set_status("Loading…")

        def _fetch():
            try:
                if key == 'unread':
                    emails = fetch_emails('INBOX', 'UNSEEN')
                elif key == 'read':
                    emails = fetch_emails('INBOX', 'SEEN')
                else:
                    emails = fetch_drafts()
                self.cache[key] = emails
                self.root.after(0, lambda: self._render_emails(key, emails))
                self.root.after(0, lambda: self.set_status(f"{len(emails)} emails loaded"))
            except Exception as ex:
                self.root.after(0, lambda: lb.delete(0, 'end'))
                self.root.after(0, lambda: lb.insert('end', f'  Error: {ex}'))
                self.root.after(0, lambda: self.set_status("Error loading"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_emails(self, key, emails):
        lb = self._widgets[key]['listbox']
        lb.delete(0, 'end')
        if not emails:
            lb.insert('end', '  No emails here!')
            return
        for e in emails:
            lb.insert('end', f"  {e['from'][:45]}  |  {e['subject'][:55]}")

    def _on_select(self, event, key):
        lb     = self._widgets[key]['listbox']
        emails = self.cache.get(key) or []
        sel    = lb.curselection()
        if not sel or sel[0] >= len(emails):
            return
        em = emails[sel[0]]
        self.selected[key] = em
        preview = self._widgets[key]['preview']
        preview.delete('1.0', 'end')
        preview.insert('end', f"From:    {em['from']}\n")
        preview.insert('end', f"To:      {em['to']}\n")
        preview.insert('end', f"Subject: {em['subject']}\n")
        preview.insert('end', f"Date:    {em['date']}\n")
        preview.insert('end', "─" * 60 + "\n")
        preview.insert('end', em['body'])

    # ── reply actions ──────────────────────────────────────────────

    def _write_reply(self, key):
        em = self.selected.get(key)
        if not em:
            messagebox.showwarning("No email selected", "Please select an email first.")
            return
        inst = self._widgets[key]['instruction'].get('1.0', 'end').strip()
        if not inst:
            messagebox.showwarning("No instruction", "Please type what you want to say.")
            return
        reply_area = self._widgets[key]['reply']
        reply_area.delete('1.0', 'end')
        reply_area.insert('end', 'Coda is writing your reply…')
        self.set_status("Coda is thinking…")
        ctx = f"From: {em['from']}\nSubject: {em['subject']}\n\n{em['body']}"

        def _do():
            text = ask_coda(ctx, inst)
            self.root.after(0, lambda: reply_area.delete('1.0', 'end'))
            self.root.after(0, lambda: reply_area.insert('end', text))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=_do, daemon=True).start()

    def _save_draft_reply(self, key):
        em = self.selected.get(key)
        if not em:
            messagebox.showwarning("No email selected", "Please select an email first.")
            return
        body = self._widgets[key]['reply'].get('1.0', 'end').strip()
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No reply", "Please write a reply first.")
            return
        try:
            save_draft(em['from'], em['subject'], body, em)
            messagebox.showinfo("Saved!", "Reply saved to Gmail Drafts.")
        except Exception as ex:
            messagebox.showerror("Error", f"Could not save draft: {ex}")

    def _send_reply(self, key):
        em = self.selected.get(key)
        if not em:
            messagebox.showwarning("No email selected", "Please select an email first.")
            return
        body = self._widgets[key]['reply'].get('1.0', 'end').strip()
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No reply", "Please write a reply first.")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{em['from']}\n\nAre you sure?"):
            try:
                send_email(em['from'], em['subject'], body, em)
                messagebox.showinfo("Sent!", "Email sent!")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")

    # ── new email actions ──────────────────────────────────────────

    def _write_new(self):
        inst = self.new_instruction.get('1.0', 'end').strip()
        if not inst:
            messagebox.showwarning("No instruction", "Please describe what you want to say.")
            return
        self.new_reply_area.delete('1.0', 'end')
        self.new_reply_area.insert('end', 'Coda is writing your email…')
        self.set_status("Coda is thinking…")

        def _do():
            text = ask_coda('', inst, mode='new')
            self.root.after(0, lambda: self.new_reply_area.delete('1.0', 'end'))
            self.root.after(0, lambda: self.new_reply_area.insert('end', text))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=_do, daemon=True).start()

    def _save_new_draft(self):
        to      = self.new_to.get().strip()
        subject = self.new_subject.get().strip()
        body    = self.new_reply_area.get('1.0', 'end').strip()
        if not to or not subject:
            messagebox.showwarning("Missing fields", "Please fill in To and Subject.")
            return
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No email", "Please write the email first.")
            return
        try:
            save_draft(to, subject, body)
            messagebox.showinfo("Saved!", "Email saved to Gmail Drafts.")
        except Exception as ex:
            messagebox.showerror("Error", f"Could not save draft: {ex}")

    def _send_new(self):
        to      = self.new_to.get().strip()
        subject = self.new_subject.get().strip()
        body    = self.new_reply_area.get('1.0', 'end').strip()
        if not to or not subject:
            messagebox.showwarning("Missing fields", "Please fill in To and Subject.")
            return
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No email", "Please write the email first.")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{to}\nSubject: {subject}\n\nAre you sure?"):
            try:
                send_email(to, subject, body)
                messagebox.showinfo("Sent!", "Email sent!")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")


def main():
    root = tk.Tk()
    app = EmailApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
