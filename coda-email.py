#!/usr/bin/python3

import requests
import json
import os
import signal
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coda_common as C

# Read fresh on every call so Preferences changes take effect immediately.
_cfg = C.email_settings

PREFS_FILE    = os.path.join(C.CONFIG_DIR, 'window.json')

SAMPLE_EMAIL = (
    "Hi,\n\n"
    "Hope you're doing well! Just wanted to quickly touch base about the proposal "
    "we discussed last week. Could you let me know if everything still looks good "
    "on your end, and whether there's anything else you need from me before we move forward?\n\n"
    "Thanks a lot,\nMike"
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

# --- Mail + contacts (shared with the `coda mail` command) ---
from coda_mail import (  # noqa: E402
    load_contacts, save_contacts, find_contact_prompt, fetch_emails, fetch_drafts,
    fetch_inbox, fetch_thread, format_thread, save_draft, send_email, cloud_write_stream)

def build_corrections_context(sender_raw, contacts, limit=3):
    # The old "learn from your edits" system was removed: storing past email
    # text as style hints made topics bleed into unrelated replies. Per-contact
    # notes in the Contacts tab replace it.
    return ''

# --- Autocomplete entry ---
class AutocompleteEntry(ttk.Entry):
    """ttk.Entry that pops up a filtered contacts dropdown while typing."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._popup  = None
        self._lb     = None
        self._emails = []
        self.bind('<KeyRelease>', self._on_key)
        self.bind('<Down>',       self._to_lb)
        self.bind('<FocusOut>',   lambda e: self.after(150, self._hide))

    def _on_key(self, event):
        if event.keysym in ('Escape', 'Return', 'Tab', 'Up', 'Down'):
            if event.keysym == 'Escape':
                self._hide()
            return
        q = self.get().strip().lower()
        if not q:
            self._hide()
            return
        seen, matches = set(), []
        for c in load_contacts():
            name  = c.get('name', '').lower()
            label = c.get('name', '')
            for em in c.get('emails', []):
                if q in name or q in em.lower():
                    key = em.lower()
                    if key not in seen:
                        seen.add(key)
                        display = f'{label} <{em}>' if label else em
                        matches.append((display, em))
        if not matches:
            self._hide()
            return
        self._show(matches)

    def _show(self, matches):
        if self._popup:
            self._popup.destroy()
        self._emails = [em for _, em in matches]
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = max(self.winfo_width(), 280)
        self._popup = tk.Toplevel(self)
        self._popup.wm_overrideredirect(True)
        self._popup.wm_attributes('-topmost', True)
        self._lb = tk.Listbox(self._popup, font=('', 9), relief='solid',
                              borderwidth=1, selectmode='single',
                              height=min(len(matches), 7))
        self._lb.pack(fill='both', expand=True)
        for disp, _ in matches:
            self._lb.insert('end', f'  {disp}')
        self._lb.bind('<ButtonRelease-1>', self._pick)
        self._lb.bind('<Return>',          self._pick)
        self._lb.bind('<Escape>',          lambda e: self._hide())
        self._lb.bind('<FocusOut>',        lambda e: self.after(150, self._hide))
        h = self._lb.winfo_reqheight() + 4
        self._popup.geometry(f'{w}x{h}+{x}+{y}')

    def _to_lb(self, event):
        if self._lb:
            self._lb.focus_set()
            if not self._lb.curselection():
                self._lb.selection_set(0)

    def _pick(self, event):
        sel = self._lb.curselection() if self._lb else ()
        if sel:
            self.delete(0, 'end')
            self.insert(0, self._emails[sel[0]])
        self._hide()

    def _hide(self):
        if self._popup:
            self._popup.destroy()
            self._popup = None
            self._lb    = None

# --- Email utilities ---
def _build_prompt(context, instruction, mode, contact_prompt, corrections_context):
    cfg = _cfg()
    name = cfg.get('USER_NAME', '').strip() or 'me'
    sign_off = f"Sign off as {name}."
    extra = ''
    if contact_prompt:
        # This is private background about the recipient, used only to shape
        # tone/word choice. A small model will otherwise paste it verbatim
        # into the email body, so make the boundary explicit.
        extra += (
            "\n\nPRIVATE NOTES ABOUT THE RECIPIENT (background only — use these to "
            "shape your tone, warmth, and word choice; do NOT quote, restate, or "
            "mention them anywhere in the email):\n"
            f"{contact_prompt}"
        )
    if corrections_context:
        extra += f"\n\n{corrections_context}"
    if mode == 'new':
        return (
            f"You are writing an email as {name}, in the first person. You ARE {name} — "
            "not an assistant. Address the email to the recipient.\n\n"
            f"WHAT {name} WANTS TO SAY:\n{instruction}{extra}\n\n"
            f"Write only the email body. No subject line. {sign_off}"
        )
    return (
        f"You are writing an email reply as {name}, in the first person. You ARE {name} — "
        "not an assistant. Reply to the conversation below.\n\n"
        f"EMAIL CONVERSATION:\n{context}\n\n"
        f"WHAT {name} WANTS TO SAY IN THE REPLY:\n{instruction}{extra}\n\n"
        f"Write only the email body. No subject line. {sign_off}"
    )

def _ollama_url():
    return C.ollama_url(_cfg()['EMAIL_OLLAMA_IP']) + '/api/generate'

def ask_coda(context, instruction, mode='reply', contact_prompt='', corrections_context=''):
    if C.email_ai_settings()[0] != 'local':
        return ''.join(ask_coda_stream(context, instruction, mode, contact_prompt, corrections_context))
    prompt = _build_prompt(context, instruction, mode, contact_prompt, corrections_context)
    try:
        resp = requests.post(
            _ollama_url(),
            json={'model': C.EMAIL_MODEL, 'prompt': prompt, 'stream': False},
            timeout=120,
        )
        data = resp.json()
        if 'response' in data:
            return data['response']
        err = data.get('error', str(data))
        return f"Model not ready: {err}\n\nOpen Preferences → Email tab → Pull Model to install coda2.0:3b."
    except Exception as e:
        return f"Error calling Coda: {e}"

def ask_coda_stream(context, instruction, mode='reply', contact_prompt='', corrections_context=''):
    prompt = _build_prompt(context, instruction, mode, contact_prompt, corrections_context)
    if C.email_ai_settings()[0] != 'local':
        yield from cloud_write_stream(prompt)
        return
    try:
        resp = requests.post(
            _ollama_url(),
            json={'model': C.EMAIL_MODEL, 'prompt': prompt, 'stream': True},
            timeout=120,
            stream=True,
        )
        for line in resp.iter_lines():
            if line:
                try:
                    obj = json.loads(line)
                    token = obj.get('response', '')
                    if token:
                        yield token
                    elif obj.get('error'):
                        err = obj['error']
                        yield f"⚠ Ollama error: {err}"
                        return
                except Exception:
                    pass
    except Exception as e:
        yield f"Error calling Coda: {e}"


# ─────────────────────────────────────────────────────────────────
class EmailApp:

    TAB_KEYS = ('inbox', 'sent', 'drafts')

    def __init__(self, root):
        self.root = root
        self._update_title()
        self.root.resizable(True, True)

        prefs = load_prefs()
        self.root.geometry(prefs.get('geometry', '920x760'))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # SIGUSR1 from the tray means "show yourself"
        signal.signal(signal.SIGUSR1,
                      lambda s, f: self.root.after(0, self._show_window))

        apply_theme(root, _cfg().get('THEME', 'light'))

        self.cache           = {k: None for k in self.TAB_KEYS}
        self.selected        = {k: None for k in self.TAB_KEYS}
        self.current_tab_key = 'inbox'
        self._coda_original  = {k: None for k in list(self.TAB_KEYS) + ['new']}
        self._gen_seq        = {k: 0    for k in list(self.TAB_KEYS) + ['new']}
        self._selected_thread = {k: None for k in self.TAB_KEYS}
        self._sel_seq         = {k: 0    for k in self.TAB_KEYS}

        self._agent_jobs = {}   # message-id → (tab, email) handed to the coding agent

        self._build_ui()
        self.load_tab('inbox')
        self.start_auto_refresh()
        self.root.after(1000, self._poll_agent_events)

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

    def _update_title(self):
        cfg = C.load_config()
        ai, model, _ = C.email_ai_settings(cfg)
        if ai == 'local':
            self.root.title("Coda — Email Agent")
        else:
            self.root.title(f"Coda — Email Agent  ·  ⚠ replies written by {model} "
                            f"({C.email_ai_company(ai, cfg.get('engine'))}, cloud)")
        btn = getattr(self, '_inbox_agent_btn', None)
        if btn is not None:
            if ai == 'agent':
                btn.config(text=f"✨  Ask {model} about my inbox")
                btn.pack(side='right', padx=(0, 6))
            else:
                btn.pack_forget()

    def _show_window(self):
        self._update_title()
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
        self._inbox_agent_btn = ttk.Button(hdr, text="", command=self._ask_agent_inbox)
        self._update_title()

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
        for key, label in [('inbox',  '📬  Inbox'),
                            ('sent',   '📤  Sent'),
                            ('drafts', '📝  Drafts')]:
            frame = ttk.Frame(self.nb, padding=4)
            self.nb.add(frame, text=f'  {label}  ')
            self._widgets[key] = self._make_email_panel(frame, key)

        new_frame = ttk.Frame(self.nb, padding=4)
        self.nb.add(new_frame, text='  ✉  New Email  ')
        self._make_new_email_panel(new_frame)

        contacts_frame = ttk.Frame(self.nb, padding=4)
        self.nb.add(contacts_frame, text='  👤  Contacts  ')
        self._make_contacts_panel(contacts_frame)

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
        write_btn = ttk.Button(btn_frm, text="✍  Write Reply",
                               command=lambda k=key: self._write_reply(k),
                               width=16)
        write_btn.pack(side='left', padx=4)
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

        return {'listbox': lb, 'preview': preview, 'instruction': instruction,
                'reply': reply_area, 'write_btn': write_btn}

    def _make_new_email_panel(self, parent):
        # To / Subject — fixed, not resizable
        fixed = ttk.Frame(parent, padding=(0, 4))
        fixed.pack(fill='x')
        ttk.Label(fixed, text="To:").grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        self.new_to = AutocompleteEntry(fixed, font=('', 10))
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
        self.new_write_btn = ttk.Button(btn_frm, text="✍  Write Email",
                                        command=self._write_new, width=16)
        self.new_write_btn.pack(side='left', padx=4)
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
        keys = list(self.TAB_KEYS) + ['new', 'contacts']
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
                if key == 'inbox':
                    emails = fetch_inbox()
                elif key == 'sent':
                    emails = fetch_emails('\\Sent', 'ALL')
                else:
                    emails = fetch_drafts()
                self.cache[key] = emails
                self.root.after(0, lambda: self._render_emails(key, emails))
                self.root.after(0, lambda: self.set_status(f"{len(emails)} emails loaded"))
            except Exception as ex:
                msg = str(ex)   # `ex` is unbound once the except block ends
                self.root.after(0, lambda: lb.delete(0, 'end'))
                self.root.after(0, lambda: lb.insert('end', f'  Error: {msg}'))
                self.root.after(0, lambda: self.set_status("Error loading"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _render_emails(self, key, emails):
        lb = self._widgets[key]['listbox']
        lb.delete(0, 'end')
        if not emails:
            lb.insert('end', '  No emails here!')
            return
        for i, e in enumerate(emails):
            unread = e.get('unread', False)
            prefix = '● ' if unread else '  '
            lb.insert('end', f"  {prefix}{e['from'][:43]}  |  {e['subject'][:53]}")
            if key == 'inbox' and not unread:
                lb.itemconfig(i, foreground='gray')

    def _on_select(self, event, key):
        lb     = self._widgets[key]['listbox']
        emails = self.cache.get(key) or []
        sel    = lb.curselection()
        if not sel or sel[0] >= len(emails):
            return
        em = emails[sel[0]]

        # When the selected email changes, discard any in-progress generation
        # and clear the instruction/reply areas so old context never bleeds in.
        if self.selected.get(key) is not em:
            self._gen_seq[key] += 1
            self._widgets[key]['instruction'].delete('1.0', 'end')
            self._widgets[key]['reply'].delete('1.0', 'end')
            self._widgets[key]['write_btn'].config(text='✍  Write Reply', state='normal')
            self._coda_original[key]  = None
            self._selected_thread[key] = None
            self._sel_seq[key] += 1

        self.selected[key] = em
        preview = self._widgets[key]['preview']
        preview.delete('1.0', 'end')
        preview.insert('end', f"From:    {em['from']}\n")
        preview.insert('end', f"To:      {em['to']}\n")
        preview.insert('end', f"Subject: {em['subject']}\n")
        preview.insert('end', f"Date:    {em['date']}\n")
        preview.insert('end', "─" * 60 + "\n")
        preview.insert('end', em['body'])

        # If this email is part of a thread, pre-fetch the full chain in the background.
        if (em.get('references') or '').strip():
            sel_seq = self._sel_seq[key]
            preview.insert('end', '\n\n  ⏳ Loading full thread…')
            threading.Thread(
                target=lambda: self._load_thread(key, em, sel_seq),
                daemon=True,
            ).start()

    def _load_thread(self, key, em, sel_seq):
        try:
            thread = fetch_thread(em)
        except Exception:
            thread = [em]
        if self._sel_seq[key] != sel_seq:
            return
        self._selected_thread[key] = thread
        self.root.after(0, lambda: self._show_thread_preview(key, thread, em))

    def _show_thread_preview(self, key, thread, selected_em):
        if self.selected.get(key) is not selected_em:
            return
        preview = self._widgets[key]['preview']
        preview.delete('1.0', 'end')
        if len(thread) <= 1:
            em = thread[0] if thread else selected_em
            preview.insert('end', f"From:    {em['from']}\n")
            preview.insert('end', f"To:      {em['to']}\n")
            preview.insert('end', f"Subject: {em['subject']}\n")
            preview.insert('end', f"Date:    {em['date']}\n")
            preview.insert('end', "─" * 60 + "\n")
            preview.insert('end', em['body'])
            return
        preview.insert('end', f"  Thread · {len(thread)} emails  ·  {selected_em['subject']}\n")
        preview.insert('end', "═" * 60 + "\n\n")
        for em in thread:
            marker = "▶ " if em.get('message_id') == selected_em.get('message_id') else "  "
            preview.insert('end', f"{marker}From:  {em['from']}\n")
            preview.insert('end', f"  Date:  {em['date']}\n")
            preview.insert('end', "─" * 40 + "\n")
            preview.insert('end', em['body'])
            preview.insert('end', "\n\n")

    # ── reply actions ──────────────────────────────────────────────

    def _write_reply(self, key):
        em = self.selected.get(key)
        if not em:
            messagebox.showwarning("No email selected", "Please select an email first.")
            return
        inst = self._widgets[key]['instruction'].get('1.0', 'end').strip()
        if C.email_ai_settings()[0] == 'agent':
            return self._agent_reply(key, em, inst)
        if not inst:
            messagebox.showwarning("No instruction", "Please type what you want to say.")
            return
        reply_area = self._widgets[key]['reply']
        write_btn  = self._widgets[key]['write_btn']

        seq = self._gen_seq[key] + 1
        self._gen_seq[key] = seq
        reply_area.delete('1.0', 'end')
        reply_area.insert('end', 'Coda is writing your reply…')
        write_btn.config(state='disabled')
        self._coda_original[key] = None
        self.set_status("Coda is thinking…")

        def _do():
            # Use pre-fetched thread if ready; otherwise fetch now (or fall back to single email).
            thread = self._selected_thread.get(key)
            if thread is None:
                if (em.get('references') or '').strip():
                    try:
                        thread = fetch_thread(em)
                        self._selected_thread[key] = thread
                    except Exception:
                        thread = [em]
                else:
                    thread = [em]
            ctx = format_thread(thread)
            contacts = load_contacts()
            cp  = find_contact_prompt(em['from'], contacts)
            cc  = build_corrections_context(em['from'], contacts)
            if self._gen_seq[key] != seq:
                return
            self.root.after(0, lambda: reply_area.delete('1.0', 'end'))
            tokens = []
            for token in ask_coda_stream(ctx, inst, contact_prompt=cp, corrections_context=cc):
                if self._gen_seq[key] != seq:
                    return
                tokens.append(token)
                t = token
                self.root.after(0, lambda t=t: reply_area.insert('end', t))
            if self._gen_seq[key] != seq:
                return
            text = ''.join(tokens)
            self.root.after(0, lambda: setattr(self, '_coda_original',
                            {**self._coda_original, key: text}))
            self.root.after(0, lambda: write_btn.config(
                            text='🔄  Refresh', state='normal'))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=_do, daemon=True).start()

    # ── writing with the user's coding agent (in its own window) ───

    def _rough_draft(self, area):
        text = area.get('1.0', 'end').strip()
        return '' if (not text or text.startswith(('Coda is writing', '⏳', '⚠'))) else text

    def _launch_agent(self, task):
        try:
            return C.open_email_agent(task)
        except Exception as ex:
            messagebox.showerror("Can't open your coding agent", str(ex))
            return None

    def _agent_reply(self, key, em, inst):
        mid = (em.get('message_id') or '').strip()
        if not mid:
            messagebox.showwarning("Can't reply", "This email has no Message-ID, so your agent can't find it.")
            return
        rough = self._rough_draft(self._widgets[key]['reply'])
        label = self._launch_agent(C.email_agent_reply_task(mid, inst, rough))
        if not label:
            return
        self._agent_jobs[mid] = (key, em)
        if not rough:
            area = self._widgets[key]['reply']
            area.delete('1.0', 'end')
            area.insert('end', f'⏳ {label} is writing in its own window. Its reply will appear here.')
        self.set_status(f"{label} is writing…")

    def _agent_new(self, to, inst):
        rough = self._rough_draft(self.new_reply_area)
        label = self._launch_agent(C.email_agent_new_task(to, self.new_subject.get().strip(), inst, rough))
        if not label:
            return
        if not rough:
            self.new_reply_area.delete('1.0', 'end')
            self.new_reply_area.insert('end', f'⏳ {label} is writing in its own window. The email will appear here.')
        self.set_status(f"{label} is writing…")

    def _ask_agent_inbox(self):
        label = self._launch_agent(C.email_agent_inbox_task())
        if label:
            self.set_status(f"{label} is reading your inbox in its own window…")

    def _poll_agent_events(self):
        try:
            names = sorted(n for n in os.listdir(C.EMAIL_EVENTS) if n.endswith('.json') and not n.startswith('.'))
        except OSError:
            names = []
        for n in names:
            path = os.path.join(C.EMAIL_EVENTS, n)
            try:
                with open(path) as f:
                    ev = json.load(f)
            except (OSError, ValueError):
                ev = None
            try:
                os.remove(path)
            except OSError:
                pass
            if ev and time.time() - ev.get('ts', 0) < 3600:
                try:
                    self._handle_agent_event(ev)
                except Exception as ex:
                    self.set_status(f"Could not show the agent's email: {ex}")
        self.root.after(1000, self._poll_agent_events)

    def _select_tab(self, key):
        keys = list(self.TAB_KEYS) + ['new', 'contacts']
        self.nb.select(keys.index(key))
        self.current_tab_key = key

    def _handle_agent_event(self, ev):
        kind = ev.get('kind')
        who = C.email_ai_settings()[1] if C.email_ai_settings()[0] == 'agent' else 'Your agent'
        if kind in ('draft', 'sent'):
            self.cache['drafts' if kind == 'draft' else 'sent'] = None
            if self.current_tab_key in ('drafts', 'sent'):
                self.load_tab(self.current_tab_key)
            self.set_status(f"✓ {who} {'saved a draft' if kind == 'draft' else 'sent an email'} "
                            f"to {ev.get('to', '')}")
            return
        if kind != 'suggest':
            return
        body = (ev.get('body') or '').strip()
        mid = (ev.get('reply_to') or '').strip()
        if mid:
            key, em = self._agent_jobs.get(mid, (None, None))
            if em is None:
                for k in self.TAB_KEYS:
                    for e in self.cache.get(k) or []:
                        if (e.get('message_id') or '').strip() == mid:
                            key, em = k, e
                            break
                    if em:
                        break
            if em is not None:
                self._select_tab(key)
                if (self.selected.get(key) or {}).get('message_id', '').strip() != mid:
                    emails = self.cache.get(key) or []
                    idx = next((i for i, e in enumerate(emails)
                                if (e.get('message_id') or '').strip() == mid), None)
                    lb = self._widgets[key]['listbox']
                    if idx is not None:
                        lb.selection_clear(0, 'end')
                        lb.selection_set(idx)
                        lb.see(idx)
                        self._on_select(None, key)
                    else:
                        self.selected[key] = em
                area = self._widgets[key]['reply']
                area.delete('1.0', 'end')
                area.insert('end', body)
                self._coda_original[key] = body
                self._widgets[key]['write_btn'].config(text='🔄  Refresh', state='normal')
                self.set_status(f"✓ {who}'s reply is ready: edit it, then Save or Send")
                self._show_window()
                return
        # A new email (or a reply to a message we can't find): New Email tab.
        self._select_tab('new')
        if ev.get('to'):
            self.new_to.delete(0, 'end')
            self.new_to.insert(0, ev['to'])
        if ev.get('subject'):
            self.new_subject.delete(0, 'end')
            self.new_subject.insert(0, ev['subject'])
        self.new_reply_area.delete('1.0', 'end')
        self.new_reply_area.insert('end', body)
        self._coda_original['new'] = body
        self.set_status(f"✓ {who}'s email is ready: check To and Subject, then Save or Send")
        self._show_window()

    def _save_draft_reply(self, key):
        em = self.selected.get(key)
        if not em:
            messagebox.showwarning("No email selected", "Please select an email first.")
            return
        body = self._widgets[key]['reply'].get('1.0', 'end').strip()
        if not body or 'Coda is writing' in body or body.startswith('⏳'):
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
        if not body or 'Coda is writing' in body or body.startswith('⏳'):
            messagebox.showwarning("No reply", "Please write a reply first.")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{em['from']}\n\nAre you sure?"):
            try:
                send_email(em['from'], em['subject'], body, em)
                self._coda_original[key] = None
                self._widgets[key]['write_btn'].config(text='✍  Write Reply')
                messagebox.showinfo("Sent!", "Email sent!")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")

    # ── new email actions ──────────────────────────────────────────

    def _write_new(self):
        inst = self.new_instruction.get('1.0', 'end').strip()
        if not inst:
            messagebox.showwarning("No instruction", "Please describe what you want to say.")
            return
        to = self.new_to.get().strip()
        if C.email_ai_settings()[0] == 'agent':
            return self._agent_new(to, inst)

        self.new_reply_area.delete('1.0', 'end')
        self.new_reply_area.insert('end', 'Coda is writing your email…')
        self.new_write_btn.config(state='disabled')
        self._coda_original['new'] = None
        self.set_status("Coda is thinking…")

        def _do():
            contacts = load_contacts()
            cp   = find_contact_prompt(to, contacts) if to else ''
            cc   = build_corrections_context(to, contacts) if to else ''
            self.root.after(0, lambda: self.new_reply_area.delete('1.0', 'end'))
            tokens = []
            for token in ask_coda_stream('', inst, mode='new', contact_prompt=cp, corrections_context=cc):
                tokens.append(token)
                t = token
                self.root.after(0, lambda t=t: self.new_reply_area.insert('end', t))
            text = ''.join(tokens)
            self.root.after(0, lambda: setattr(self, '_coda_original',
                            {**self._coda_original, 'new': text}))
            self.root.after(0, lambda: self.new_write_btn.config(
                            text='🔄  Refresh', state='normal'))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=_do, daemon=True).start()

    def _save_new_draft(self):
        to      = self.new_to.get().strip()
        subject = self.new_subject.get().strip()
        body    = self.new_reply_area.get('1.0', 'end').strip()
        if not to or not subject:
            messagebox.showwarning("Missing fields", "Please fill in To and Subject.")
            return
        if not body or 'Coda is writing' in body or body.startswith('⏳'):
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
        if not body or 'Coda is writing' in body or body.startswith('⏳'):
            messagebox.showwarning("No email", "Please write the email first.")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{to}\nSubject: {subject}\n\nAre you sure?"):
            try:
                send_email(to, subject, body)
                self._coda_original['new'] = None
                self.new_write_btn.config(text='✍  Write Email')
                messagebox.showinfo("Sent!", "Email sent!")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")


    # ── Contacts tab ───────────────────────────────────────────────

    def _make_contacts_panel(self, parent):
        self._contacts        = load_contacts()
        self._cur_contact_idx = None

        # Top bar: combobox selector + New / Delete
        top = ttk.Frame(parent, padding=(0, 0, 0, 6))
        top.pack(fill='x')
        ttk.Label(top, text="Contact:").pack(side='left', padx=(0, 6))
        self._contact_var   = tk.StringVar()
        self._contact_combo = ttk.Combobox(top, textvariable=self._contact_var,
                                           state='readonly', width=36)
        self._contact_combo.pack(side='left', padx=(0, 8))
        self._contact_combo.bind('<<ComboboxSelected>>', self._on_contact_select)
        ttk.Button(top, text='+ New',  command=self._new_contact,    width=8).pack(side='left', padx=2)
        ttk.Button(top, text='Delete', command=self._delete_contact, width=8).pack(side='left', padx=2)

        ttk.Separator(parent).pack(fill='x', pady=(0, 6))

        # Vertical split: form on top, preview on bottom
        vpaned = tk.PanedWindow(parent, orient='vertical',
                                sashwidth=5, sashrelief='raised')
        vpaned.pack(fill='both', expand=True)

        # ── Form ──
        form = ttk.LabelFrame(vpaned, text="Contact rule", padding=8)
        vpaned.add(form, minsize=150)

        ttk.Label(form, text="Email addresses\n(comma-separated):").grid(row=0, column=0, sticky='w', pady=3)
        self._c_emails = ttk.Entry(form, font=('', 10))
        self._c_emails.grid(row=0, column=1, sticky='ew', pady=3)
        self._c_emails.bind('<KeyRelease>', lambda e: self._update_name_state())

        ttk.Label(form, text="Name (optional):").grid(row=1, column=0, sticky='w', pady=3)
        self._c_name = ttk.Entry(form, font=('', 10))
        self._c_name.grid(row=1, column=1, sticky='ew', pady=3)

        ttk.Label(form, text="Custom prompt:").grid(row=2, column=0, sticky='nw', pady=3)
        prompt_cell = ttk.Frame(form)
        prompt_cell.grid(row=2, column=1, sticky='nsew', pady=3)
        prompt_cell.columnconfigure(0, weight=1)
        prompt_cell.rowconfigure(0, weight=1)
        self._c_prompt = scrolledtext.ScrolledText(prompt_cell, font=('', 10), wrap='word',
                                                    relief='flat', borderwidth=1, height=4)
        self._c_prompt.grid(row=0, column=0, sticky='nsew')
        ttk.Label(prompt_cell,
                  text="Notes about this contact, written from your point of view — used to "
                       "shape tone, not inserted into the email.\n"
                       "e.g. \"My wife — warm, affectionate.\"  or  \"Strictly formal, business only.\"",
                  foreground='gray', font=('', 8), wraplength=520, justify='left'
                  ).grid(row=1, column=0, sticky='w', pady=(2, 0))

        ttk.Button(form, text='💾  Save Contact',
                   command=self._save_contact, width=18).grid(
                       row=3, column=1, sticky='e', pady=(6, 2))

        ttk.Label(form, text="Learned corrections:").grid(row=4, column=0, sticky='w', pady=3)
        self._c_corrections_lbl = ttk.Label(form, text="none yet", foreground='gray', font=('', 9))
        self._c_corrections_lbl.grid(row=4, column=1, sticky='w', pady=3)

        form.columnconfigure(1, weight=1)
        form.rowconfigure(2, weight=1)

        # ── Preview ──
        prev_frame = ttk.LabelFrame(vpaned, text="Example reply", padding=8)
        vpaned.add(prev_frame, minsize=150)

        ttk.Label(prev_frame, text="Test email:").pack(anchor='w')
        self._c_test_in = scrolledtext.ScrolledText(prev_frame, font=('', 9), wrap='word',
                                                     relief='flat', borderwidth=1, height=4)
        self._c_test_in.insert('end', SAMPLE_EMAIL)
        self._c_test_in.pack(fill='x', pady=(2, 6))

        ttk.Button(prev_frame, text='✍  Generate Example',
                   command=self._preview_contact, width=20).pack(anchor='w')

        self._c_preview_out = scrolledtext.ScrolledText(prev_frame, font=('', 9), wrap='word',
                                                         relief='flat', borderwidth=1)
        self._c_preview_out.pack(fill='both', expand=True, pady=(6, 0))

        self._refresh_contact_list()

    def _refresh_contact_list(self):
        labels = []
        for c in self._contacts:
            name  = c.get('name', '')
            first = (c.get('emails') or [''])[0]
            labels.append(f"{name} <{first}>" if name else first)
        self._contact_combo['values'] = labels
        if self._cur_contact_idx is not None and self._cur_contact_idx < len(labels):
            self._contact_combo.current(self._cur_contact_idx)
        elif not labels:
            self._contact_combo.set('')

    def _on_contact_select(self, event=None):
        idx = self._contact_combo.current()
        if idx < 0 or idx >= len(self._contacts):
            return
        self._cur_contact_idx = idx
        c = self._contacts[idx]
        self._c_emails.delete(0, 'end')
        self._c_emails.insert(0, ', '.join(c.get('emails', [])))
        self._c_name.delete(0, 'end')
        self._c_name.insert(0, c.get('name', ''))
        self._c_prompt.delete('1.0', 'end')
        self._c_prompt.insert('end', c.get('prompt', ''))
        self._update_name_state()
        n = len(c.get('corrections', []))
        self._c_corrections_lbl.config(
            text=f"{n} correction{'s' if n != 1 else ''} saved" if n else "none yet",
            foreground='gray')

    def _new_contact(self):
        self._cur_contact_idx = None
        self._contact_combo.set('')
        self._c_emails.delete(0, 'end')
        self._c_name.delete(0, 'end')
        self._c_prompt.delete('1.0', 'end')
        self._update_name_state()
        self._c_corrections_lbl.config(text='none yet', foreground='gray')
        self._c_emails.focus_set()

    def _delete_contact(self):
        if self._cur_contact_idx is None:
            messagebox.showwarning("Nothing selected", "Select a contact first.")
            return
        c     = self._contacts[self._cur_contact_idx]
        label = c.get('name') or (c.get('emails') or ['?'])[0]
        if not messagebox.askyesno("Delete?", f"Delete contact: {label}?"):
            return
        del self._contacts[self._cur_contact_idx]
        save_contacts(self._contacts)
        self._cur_contact_idx = None
        self._refresh_contact_list()
        self._contact_combo.set('')
        self._c_emails.delete(0, 'end')
        self._c_name.delete(0, 'end')
        self._c_prompt.delete('1.0', 'end')
        self._update_name_state()
        self._c_corrections_lbl.config(text='none yet', foreground='gray')

    def _update_name_state(self):
        count = len([e for e in self._c_emails.get().split(',') if e.strip()])
        if count >= 2:
            self._c_name.delete(0, 'end')
            self._c_name.config(state='disabled')
        else:
            self._c_name.config(state='normal')

    def _save_contact(self):
        name       = self._c_name.get().strip()
        emails_raw = self._c_emails.get().strip()
        prompt     = self._c_prompt.get('1.0', 'end').strip()
        if not emails_raw:
            messagebox.showwarning("Missing email", "Enter at least one email address.")
            return
        emails = [e.strip() for e in emails_raw.split(',') if e.strip()]
        entry  = {'name': name, 'emails': emails, 'prompt': prompt}
        if self._cur_contact_idx is not None:
            self._contacts[self._cur_contact_idx] = entry
        else:
            self._contacts.append(entry)
            self._cur_contact_idx = len(self._contacts) - 1
        save_contacts(self._contacts)
        self._refresh_contact_list()
        messagebox.showinfo("Saved", "Contact rule saved!")

    def _preview_contact(self):
        prompt = self._c_prompt.get('1.0', 'end').strip()
        if not prompt:
            messagebox.showwarning("No prompt", "Enter a custom prompt first.")
            return
        test_email = self._c_test_in.get('1.0', 'end').strip()
        if not test_email:
            messagebox.showwarning("No test email", "Enter a test email to try.")
            return
        self._c_preview_out.delete('1.0', 'end')
        self._c_preview_out.insert('end', 'Generating example…')

        def _do():
            text = ask_coda(test_email, 'Write a reply', contact_prompt=prompt)
            self.root.after(0, lambda: self._c_preview_out.delete('1.0', 'end'))
            self.root.after(0, lambda: self._c_preview_out.insert('end', text))

        threading.Thread(target=_do, daemon=True).start()


def main():
    root = tk.Tk()
    app = EmailApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
