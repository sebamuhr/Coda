#!/usr/bin/python3

import imaplib
import smtplib
import email
import email.utils
import requests
import re
import json
import os
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

# --- Load config ---
config = {}
with open('/home/sebastian/.config/coda/email.conf') as f:
    for line in f:
        if '=' in line:
            k, v = line.strip().split('=', 1)
            config[k] = v

EMAIL = config['EMAIL']
APP_PASSWORD = config['APP_PASSWORD']
IMAP_SERVER = config['IMAP_SERVER']
SMTP_SERVER = config.get('SMTP_SERVER', 'smtp.gmail.com')
OLLAMA_IP = config.get('OLLAMA_IP', 'localhost')
MODEL = config.get('MODEL', 'coda:2.0')
PREFS_FILE = os.path.expanduser('~/.config/coda/window.json')
AUTO_REFRESH_MINUTES = 5

def save_prefs(geometry):
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    with open(PREFS_FILE, 'w') as f:
        json.dump({'geometry': geometry}, f)

def load_prefs():
    try:
        with open(PREFS_FILE) as f:
            return json.load(f)
    except:
        return {}

def decode_str(s):
    if s is None:
        return ''
    decoded = decode_header(s)
    result = ''
    for part, enc in decoded:
        if isinstance(part, bytes):
            result += part.decode(enc or 'utf-8', errors='replace')
        else:
            result += part
    return result

def strip_html(html):
    html = re.sub(r'<(style|script)[^>]*>.*?</(style|script)>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<(br|p|div|tr|li)[^>]*>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()

def get_body(msg):
    plain = ''
    html = ''
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain' and not plain:
                try:
                    plain = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    pass
            elif ct == 'text/html' and not html:
                try:
                    html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    pass
    else:
        try:
            raw = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            if msg.get_content_type() == 'text/html':
                html = raw
            else:
                plain = raw
        except:
            pass
    if plain:
        return plain[:3000]
    elif html:
        return strip_html(html)[:3000]
    return ''

def fetch_emails(folder='INBOX', criteria='UNSEEN'):
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, APP_PASSWORD)
    mail.select(folder)
    _, data = mail.search(None, criteria)
    ids = data[0].split()[-15:]
    emails = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        emails.append({
            'id': eid,
            'from': decode_str(msg['From']),
            'to': decode_str(msg['To']),
            'subject': decode_str(msg['Subject']),
            'date': decode_str(msg['Date']),
            'body': get_body(msg),
            'message_id': msg.get('Message-ID', ''),
            'references': msg.get('References', ''),
        })
    mail.logout()
    return emails

def fetch_drafts():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, APP_PASSWORD)
    mail.select('"[Gmail]/Drafts"')
    _, data = mail.search(None, 'ALL')
    ids = data[0].split()[-15:]
    emails = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        emails.append({
            'id': eid,
            'from': decode_str(msg['From']),
            'to': decode_str(msg['To']),
            'subject': decode_str(msg['Subject']),
            'date': decode_str(msg['Date']),
            'body': get_body(msg),
            'message_id': msg.get('Message-ID', ''),
            'references': msg.get('References', ''),
        })
    mail.logout()
    return emails

def build_msg(to, subject, body, selected_email=None):
    msg = MIMEMultipart('alternative')
    msg['From'] = EMAIL
    msg['To'] = to
    if selected_email and not subject.startswith('Re:'):
        subject = 'Re: ' + subject
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    if selected_email and selected_email.get('message_id'):
        msg['In-Reply-To'] = selected_email['message_id']
        refs = selected_email.get('references', '')
        msg['References'] = (refs + ' ' + selected_email['message_id']).strip()
    msg.attach(MIMEText(body, 'plain'))
    return msg

def save_draft(to, subject, body, selected_email=None):
    msg = build_msg(to, subject, body, selected_email)
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, APP_PASSWORD)
    mail.append('"[Gmail]/Drafts"', '', None, msg.as_bytes())
    mail.logout()

def send_email(to, subject, body, selected_email=None):
    msg = build_msg(to, subject, body, selected_email)
    with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
        smtp.login(EMAIL, APP_PASSWORD)
        smtp.sendmail(EMAIL, to, msg.as_bytes())

def ask_coda(context, instruction, mode='reply'):
    if mode == 'new':
        prompt = f"""You are an email assistant. Write a professional email based on the instruction below.

INSTRUCTION:
{instruction}

Write only the email body. No subject line. Sign off as Sebastian."""
    else:
        prompt = f"""You are an email assistant. Based on the email conversation below, write a professional reply.

EMAIL CONTEXT:
{context}

USER INSTRUCTION:
{instruction}

Write only the email body. No subject line. Sign off as Sebastian."""
    try:
        response = requests.post(
            f'http://{OLLAMA_IP}:11434/api/generate',
            json={'model': MODEL, 'prompt': prompt, 'stream': False},
            timeout=120
        )
        return response.json()['response']
    except Exception as e:
        return f"Error calling Coda: {e}"


class EmailApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Coda Email Assistant")
        self.root.resizable(True, True)
        self.root.configure(bg='#1a1a2e')

        prefs = load_prefs()
        self.root.geometry(prefs.get('geometry', '900x750'))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Cache — emails loaded once per tab, only refreshed on demand
        self.cache = {'unread': None, 'read': None, 'drafts': None}
        self.selected_email = None
        self.current_tab = 'unread'

        self.build_ui()
        self.load_tab('unread')
        self.start_auto_refresh()

    def on_close(self):
        save_prefs(self.root.geometry())
        self.root.withdraw()

    def start_auto_refresh(self):
        def refresh_loop():
            self.refresh_current_tab()
            self.root.after(AUTO_REFRESH_MINUTES * 60 * 1000, self.start_auto_refresh)
        self.root.after(AUTO_REFRESH_MINUTES * 60 * 1000, refresh_loop)

    def refresh_current_tab(self):
        if self.current_tab != 'new':
            self.cache[self.current_tab] = None
            self.load_tab(self.current_tab)

    def build_ui(self):
        tk.Label(self.root, text="Coda Email Assistant", font=('DejaVu Sans', 16, 'bold'),
                bg='#1a1a2e', fg='#00d4ff').pack(pady=8)

        tab_frame = tk.Frame(self.root, bg='#1a1a2e')
        tab_frame.pack(fill='x', padx=20, pady=4)
        self.tab_buttons = {}
        for label, key in [('📬 Unread', 'unread'), ('📖 Read', 'read'), ('📝 Drafts', 'drafts'), ('✉ New Email', 'new')]:
            btn = tk.Button(tab_frame, text=label,
                           command=lambda k=key: self.load_tab(k),
                           bg='#0f0f1a', fg='#aaaaaa',
                           font=('DejaVu Sans', 10), relief='flat', padx=15, pady=6)
            btn.pack(side='left', padx=2)
            self.tab_buttons[key] = btn

        # Refresh button
        self.refresh_btn = tk.Button(tab_frame, text="🔄", command=self.force_refresh,
                                      bg='#0f0f1a', fg='#aaaaaa',
                                      font=('DejaVu Sans', 10), relief='flat', padx=10, pady=6)
        self.refresh_btn.pack(side='left', padx=2)

        # Status label
        self.status_label = tk.Label(tab_frame, text="", font=('DejaVu Sans', 8),
                                      bg='#1a1a2e', fg='#555555')
        self.status_label.pack(side='right', padx=10)

        # Global scrollable canvas
        outer = tk.Frame(self.root, bg='#1a1a2e')
        outer.pack(fill='both', expand=True, padx=(20,0), pady=6)

        global_scrollbar = tk.Scrollbar(outer, orient='vertical')
        global_scrollbar.pack(side='right', fill='y')

        self.canvas = tk.Canvas(outer, bg='#1a1a2e', highlightthickness=0,
                                yscrollcommand=global_scrollbar.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        global_scrollbar.config(command=self.canvas.yview)

        self.content_frame = tk.Frame(self.canvas, bg='#1a1a2e')
        self.canvas_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor='nw')

        self.content_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.canvas.bind_all('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind_all('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))

        self.build_reply_view()
        self.build_new_email_view()
        self.show_reply_view()

    def build_reply_view(self):
        self.reply_view = tk.Frame(self.content_frame, bg='#1a1a2e')

        paned = tk.PanedWindow(self.reply_view, orient='vertical', bg='#333355',
                               sashwidth=6, sashrelief='raised')
        paned.pack(fill='both', expand=True)

        # Email list
        top = tk.Frame(paned, bg='#1a1a2e')
        paned.add(top, minsize=80)
        tk.Label(top, text="Emails:", font=('DejaVu Sans', 9), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w')
        list_scroll = tk.Scrollbar(top)
        list_scroll.pack(side='right', fill='y')
        self.listbox = tk.Listbox(top, bg='#0f0f1a', fg='white',
                                   selectbackground='#00d4ff', selectforeground='black',
                                   font=('DejaVu Sans', 9), relief='flat', bd=0,
                                   yscrollcommand=list_scroll.set)
        self.listbox.pack(fill='both', expand=True)
        list_scroll.config(command=self.listbox.yview)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        # Email preview
        mid = tk.Frame(paned, bg='#1a1a2e')
        paned.add(mid, minsize=80)
        tk.Label(mid, text="Email content:", font=('DejaVu Sans', 9), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w')
        self.preview = scrolledtext.ScrolledText(mid, bg='#0f0f1a', fg='#cccccc',
                                                  font=('DejaVu Sans', 9), relief='flat', bd=5, wrap='word')
        self.preview.pack(fill='both', expand=True)

        # Instruction panel
        inst_frame = tk.Frame(paned, bg='#1a1a2e')
        paned.add(inst_frame, minsize=80)
        tk.Label(inst_frame, text="What do you want to say?", font=('DejaVu Sans', 9), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w')
        self.instruction = scrolledtext.ScrolledText(inst_frame, bg='#0f0f1a', fg='white',
                                                      font=('DejaVu Sans', 10), relief='flat', bd=5,
                                                      insertbackground='white', wrap='word')
        self.instruction.pack(fill='both', expand=True, pady=4)

        # Buttons panel — fixed size
        btn_panel = tk.Frame(paned, bg='#1a1a2e')
        paned.add(btn_panel, minsize=50)
        btn_frame = tk.Frame(btn_panel, bg='#1a1a2e')
        btn_frame.pack(anchor='w', pady=4)
        tk.Button(btn_frame, text="✍ Write Reply", command=self.write_reply,
                 bg='#00d4ff', fg='black', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)
        tk.Button(btn_frame, text="💾 Save to Drafts", command=self.save_to_drafts,
                 bg='#00ff99', fg='black', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)
        tk.Button(btn_frame, text="🚀 Send Now", command=self.send_now,
                 bg='#ff6600', fg='white', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)

        # Coda's reply — resizable panel
        reply_panel = tk.Frame(paned, bg='#1a1a2e')
        paned.add(reply_panel, minsize=80)
        tk.Label(reply_panel, text="Coda's reply:", font=('DejaVu Sans', 9), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w')
        self.reply_area = scrolledtext.ScrolledText(reply_panel, bg='#0f0f1a', fg='white',
                                                     font=('DejaVu Sans', 9), relief='flat', bd=5, wrap='word')
        self.reply_area.pack(fill='both', expand=True)

    def build_new_email_view(self):
        self.new_view = tk.Frame(self.content_frame, bg='#1a1a2e')

        # To + Subject — fixed, not resizable
        fixed = tk.Frame(self.new_view, bg='#1a1a2e')
        fixed.pack(fill='x', pady=(4,0))
        tk.Label(fixed, text="To:", font=('DejaVu Sans', 10), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', pady=(8,0))
        self.new_to = tk.Entry(fixed, bg='#0f0f1a', fg='white', font=('DejaVu Sans', 10),
                               relief='flat', bd=5, insertbackground='white')
        self.new_to.pack(fill='x', pady=2)
        tk.Label(fixed, text="Subject:", font=('DejaVu Sans', 10), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', pady=(4,0))
        self.new_subject = tk.Entry(fixed, bg='#0f0f1a', fg='white', font=('DejaVu Sans', 10),
                                    relief='flat', bd=5, insertbackground='white')
        self.new_subject.pack(fill='x', pady=2)

        # Resizable panels below
        paned = tk.PanedWindow(self.new_view, orient='vertical', bg='#333355',
                               sashwidth=6, sashrelief='raised')
        paned.pack(fill='both', expand=True)

        # Instruction
        inst_frame = tk.Frame(paned, bg='#1a1a2e')
        paned.add(inst_frame, minsize=80)
        tk.Label(inst_frame, text="What do you want to say?", font=('DejaVu Sans', 10), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w', pady=(4,0))
        self.new_instruction = scrolledtext.ScrolledText(inst_frame, bg='#0f0f1a', fg='white',
                                                          font=('DejaVu Sans', 10), relief='flat', bd=5,
                                                          insertbackground='white', wrap='word')
        self.new_instruction.pack(fill='both', expand=True, pady=2)

        # Buttons panel — fixed
        btn_panel = tk.Frame(paned, bg='#1a1a2e')
        paned.add(btn_panel, minsize=50)
        btn_frame = tk.Frame(btn_panel, bg='#1a1a2e')
        btn_frame.pack(anchor='w', pady=8)
        tk.Button(btn_frame, text="✍ Write Email", command=self.write_new,
                 bg='#00d4ff', fg='black', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)
        tk.Button(btn_frame, text="💾 Save to Drafts", command=self.save_new_draft,
                 bg='#00ff99', fg='black', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)
        tk.Button(btn_frame, text="🚀 Send Now", command=self.send_new,
                 bg='#ff6600', fg='white', font=('DejaVu Sans', 10, 'bold'),
                 relief='flat', padx=15, pady=6).pack(side='left', padx=4)

        # Coda's email — resizable
        reply_panel = tk.Frame(paned, bg='#1a1a2e')
        paned.add(reply_panel, minsize=80)
        tk.Label(reply_panel, text="Coda's email:", font=('DejaVu Sans', 9), bg='#1a1a2e', fg='#aaaaaa').pack(anchor='w')
        self.new_reply_area = scrolledtext.ScrolledText(reply_panel, bg='#0f0f1a', fg='white',
                                                         font=('DejaVu Sans', 9), relief='flat', bd=5, wrap='word')
        self.new_reply_area.pack(fill='both', expand=True)

    def show_reply_view(self):
        self.new_view.pack_forget()
        self.reply_view.pack(fill='both', expand=True)

    def show_new_view(self):
        self.reply_view.pack_forget()
        self.new_view.pack(fill='both', expand=True)

    def set_status(self, msg):
        self.status_label.config(text=msg)
        self.root.update()

    def force_refresh(self):
        if self.current_tab != 'new':
            self.cache[self.current_tab] = None
            self.load_tab(self.current_tab)

    def load_tab(self, tab):
        self.current_tab = tab
        for key, btn in self.tab_buttons.items():
            btn.configure(bg='#00d4ff' if key == tab else '#0f0f1a',
                         fg='black' if key == tab else '#aaaaaa')
        if tab == 'new':
            self.show_new_view()
            return

        self.show_reply_view()

        # Use cache if available
        if self.cache[tab] is not None:
            self.render_emails(self.cache[tab])
            self.set_status(f"Cached — click 🔄 to refresh")
            return

        # Load in background thread
        self.listbox.delete(0, 'end')
        self.listbox.insert('end', '  Loading...')
        self.set_status("Loading...")
        self.root.update()

        def do_fetch():
            try:
                if tab == 'unread':
                    emails = fetch_emails('INBOX', 'UNSEEN')
                elif tab == 'read':
                    emails = fetch_emails('INBOX', 'SEEN')
                elif tab == 'drafts':
                    emails = fetch_drafts()
                self.cache[tab] = emails
                self.root.after(0, lambda: self.render_emails(emails))
                self.root.after(0, lambda: self.set_status(f"{len(emails)} emails loaded"))
            except Exception as ex:
                self.root.after(0, lambda: self.listbox.delete(0, 'end'))
                self.root.after(0, lambda: self.listbox.insert('end', f'  Error: {ex}'))
                self.root.after(0, lambda: self.set_status("Error loading"))

        threading.Thread(target=do_fetch, daemon=True).start()

    def render_emails(self, emails):
        self.listbox.delete(0, 'end')
        if not emails:
            self.listbox.insert('end', '  No emails here!')
        for e in emails:
            self.listbox.insert('end', f"  {e['from'][:45]}  |  {e['subject'][:55]}")

    def on_select(self, event):
        sel = self.listbox.curselection()
        emails = self.cache.get(self.current_tab) or []
        if sel and sel[0] < len(emails):
            self.selected_email = emails[sel[0]]
            self.preview.delete('1.0', 'end')
            self.preview.insert('end', f"From:    {self.selected_email['from']}\n")
            self.preview.insert('end', f"To:      {self.selected_email['to']}\n")
            self.preview.insert('end', f"Subject: {self.selected_email['subject']}\n")
            self.preview.insert('end', f"Date:    {self.selected_email['date']}\n")
            self.preview.insert('end', "─" * 60 + "\n")
            self.preview.insert('end', self.selected_email['body'])

    def write_reply(self):
        if not self.selected_email:
            messagebox.showwarning("No email selected", "Please select an email first!")
            return
        instruction = self.instruction.get('1.0', 'end').strip()
        if not instruction:
            messagebox.showwarning("No instruction", "Please type what you want to say!")
            return
        self.reply_area.delete('1.0', 'end')
        self.reply_area.insert('end', 'Coda is writing your reply...')
        self.set_status("Coda is thinking...")
        context = f"From: {self.selected_email['from']}\nSubject: {self.selected_email['subject']}\n\n{self.selected_email['body']}"

        def do_write():
            reply = ask_coda(context, instruction)
            self.root.after(0, lambda: self.reply_area.delete('1.0', 'end'))
            self.root.after(0, lambda: self.reply_area.insert('end', reply))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=do_write, daemon=True).start()

    def save_to_drafts(self):
        if not self.selected_email:
            messagebox.showwarning("No email selected", "Please select an email first!")
            return
        reply = self.reply_area.get('1.0', 'end').strip()
        if not reply or 'Coda is writing' in reply:
            messagebox.showwarning("No reply", "Please write a reply first!")
            return
        try:
            save_draft(self.selected_email['from'], self.selected_email['subject'], reply, self.selected_email)
            messagebox.showinfo("Saved!", "Reply saved to Gmail Drafts!")
        except Exception as ex:
            messagebox.showerror("Error", f"Could not save draft: {ex}")

    def send_now(self):
        if not self.selected_email:
            messagebox.showwarning("No email selected", "Please select an email first!")
            return
        reply = self.reply_area.get('1.0', 'end').strip()
        if not reply or 'Coda is writing' in reply:
            messagebox.showwarning("No reply", "Please write a reply first!")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{self.selected_email['from']}\n\nAre you sure?"):
            try:
                send_email(self.selected_email['from'], self.selected_email['subject'], reply, self.selected_email)
                messagebox.showinfo("Sent!", "Email sent! 🚀")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")

    def write_new(self):
        instruction = self.new_instruction.get('1.0', 'end').strip()
        if not instruction:
            messagebox.showwarning("No instruction", "Please describe what you want to say!")
            return
        self.new_reply_area.delete('1.0', 'end')
        self.new_reply_area.insert('end', 'Coda is writing your email...')
        self.set_status("Coda is thinking...")

        def do_write_new():
            reply = ask_coda('', instruction, mode='new')
            self.root.after(0, lambda: self.new_reply_area.delete('1.0', 'end'))
            self.root.after(0, lambda: self.new_reply_area.insert('end', reply))
            self.root.after(0, lambda: self.set_status("Done!"))

        threading.Thread(target=do_write_new, daemon=True).start()

    def save_new_draft(self):
        to = self.new_to.get().strip()
        subject = self.new_subject.get().strip()
        body = self.new_reply_area.get('1.0', 'end').strip()
        if not to or not subject:
            messagebox.showwarning("Missing fields", "Please fill in To and Subject!")
            return
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No email", "Please write the email first!")
            return
        try:
            save_draft(to, subject, body)
            messagebox.showinfo("Saved!", "Email saved to Gmail Drafts!")
        except Exception as ex:
            messagebox.showerror("Error", f"Could not save draft: {ex}")

    def send_new(self):
        to = self.new_to.get().strip()
        subject = self.new_subject.get().strip()
        body = self.new_reply_area.get('1.0', 'end').strip()
        if not to or not subject:
            messagebox.showwarning("Missing fields", "Please fill in To and Subject!")
            return
        if not body or 'Coda is writing' in body:
            messagebox.showwarning("No email", "Please write the email first!")
            return
        if messagebox.askyesno("Send?", f"Send to:\n{to}\nSubject: {subject}\n\nAre you sure?"):
            try:
                send_email(to, subject, body)
                messagebox.showinfo("Sent!", "Email sent! 🚀")
            except Exception as ex:
                messagebox.showerror("Error", f"Could not send: {ex}")

if __name__ == '__main__':
    root = tk.Tk()
    app = EmailApp(root)
    root.mainloop()
