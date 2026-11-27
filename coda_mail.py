"""Mail + contacts — no GUI. Used by the Email Agent window and by `coda mail`."""
import email
import datetime
import email.utils
import html as _html
import imaplib
import json
import os
import re
import smtplib
import sys
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coda_common as C  # noqa: E402

_cfg = C.email_settings
CONTACTS_FILE = os.path.join(C.CONFIG_DIR, 'contacts.json')


# --- Contacts ---
def load_contacts():
    try:
        with open(CONTACTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_contacts(contacts):
    C.ensure_private_dir(C.CONFIG_DIR)
    fd = os.open(CONTACTS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(contacts, f, indent=2)

def find_contact_prompt(sender_raw, contacts):
    sender = sender_raw.lower()
    for c in contacts:
        for addr in c.get('emails', []):
            if addr.lower().strip() in sender:
                return c.get('prompt', '')
    return ''

def find_contact_idx(sender_raw, contacts):
    sender = sender_raw.lower()
    for i, c in enumerate(contacts):
        for addr in c.get('emails', []):
            if addr.lower().strip() in sender:
                return i
    return None


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

_FOLDER_CACHE = {}
_FOLDER_FALLBACK = {'\\Sent': '"[Gmail]/Sent Mail"', '\\Drafts': '"[Gmail]/Drafts"'}

def special_folder(mail, flag):
    """Find the Sent/Drafts folder on any provider via IMAP special-use flags
    (RFC 6154), e.g. "[Gmail]/Sent Mail" on Gmail, "Sent" on Outlook/Yahoo."""
    key = (_cfg().get('IMAP_SERVER'), flag)
    if key in _FOLDER_CACHE:
        return _FOLDER_CACHE[key]
    found = None
    try:
        _, lines = mail.list()
        for raw in lines or []:
            line = raw.decode(errors='ignore') if isinstance(raw, bytes) else str(raw)
            m = re.match(r'\((?P<flags>[^)]*)\) (?:"[^"]*"|NIL) (?P<name>.+)$', line)
            if m and flag.lower() in m.group('flags').lower().split():
                name = m.group('name').strip()
                found = name if name.startswith('"') else f'"{name}"'
                break
    except Exception:
        pass
    found = found or _FOLDER_FALLBACK[flag]
    _FOLDER_CACHE[key] = found
    return found

def fetch_emails(folder='INBOX', criteria='UNSEEN', count=None):
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    if folder.startswith('\\'):
        folder = special_folder(mail, folder)
    mail.select(folder, readonly=True)
    _, data = mail.search(None, criteria)
    count = count or int(cfg.get('SYNC_COUNT', '15'))
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

def fetch_drafts(count=None):
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    mail.select(special_folder(mail, '\\Drafts'), readonly=True)
    _, data = mail.search(None, 'ALL')
    count = count or int(cfg.get('SYNC_COUNT', '15'))
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

def fetch_inbox(count=None):
    """Fetch recent INBOX emails; marks each one with 'unread': True/False."""
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    mail.select('INBOX', readonly=True)
    _, unseen_data = mail.search(None, 'UNSEEN')
    unseen_ids = set(unseen_data[0].split()) if unseen_data[0] else set()
    _, all_data = mail.search(None, 'ALL')
    count = count or int(cfg.get('SYNC_COUNT', '15'))
    ids = all_data[0].split()[-count:]
    result = []
    for eid in reversed(ids):
        _, msg_data = mail.fetch(eid, '(BODY.PEEK[])')
        msg = email.message_from_bytes(msg_data[0][1])
        result.append({
            'id':         eid,
            'from':       decode_str(msg['From']),
            'to':         decode_str(msg['To']),
            'subject':    decode_str(msg['Subject']),
            'date':       decode_str(msg['Date']),
            'body':       get_body(msg),
            'message_id': msg.get('Message-ID', ''),
            'references': msg.get('References', ''),
            'unread':     eid in unseen_ids,
        })
    mail.logout()
    return result


def fetch_thread(selected_email):
    """Fetch every email in the same conversation thread (INBOX + Sent Mail)."""
    own_id   = (selected_email.get('message_id') or '').strip()
    refs_str = (selected_email.get('references')  or '').strip()
    thread_ids = [i for i in refs_str.split() if i]
    if own_id and own_id not in thread_ids:
        thread_ids.append(own_id)
    if len(thread_ids) <= 1:
        return [selected_email]

    cfg = _cfg()
    try:
        mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
        mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    except Exception:
        return [selected_email]

    found = {}
    for folder in ['INBOX', special_folder(mail, '\\Sent')]:
        try:
            if mail.select(folder, readonly=True)[0] != 'OK':
                continue
            for mid in thread_ids:
                bare = mid.strip('<>').replace('"', '')
                try:
                    _, data = mail.search(None, f'HEADER Message-ID "{bare}"')
                    for eid in (data[0].split() if data[0] else []):
                        try:
                            _, md = mail.fetch(eid, '(BODY.PEEK[])')
                            if not md or not md[0]:
                                continue
                            msg = email.message_from_bytes(md[0][1])
                            k = (msg.get('Message-ID') or '').strip()
                            if k and k not in found:
                                found[k] = {
                                    'from':       decode_str(msg['From']),
                                    'to':         decode_str(msg['To']),
                                    'subject':    decode_str(msg['Subject']),
                                    'date':       decode_str(msg['Date']),
                                    'body':       get_body(msg),
                                    'message_id': k,
                                    'references': msg.get('References', ''),
                                }
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    try:
        mail.logout()
    except Exception:
        pass

    if not found:
        return [selected_email]
    if own_id and own_id not in found:
        found[own_id] = selected_email

    def _key(em):
        try:
            return email.utils.parsedate_to_datetime(em['date'])
        except Exception:
            return datetime.datetime.min

    return sorted(found.values(), key=_key)


def format_thread(thread):
    """Format a list of emails as a chronological conversation context."""
    if len(thread) == 1:
        em = thread[0]
        return f"From: {em['from']}\nSubject: {em['subject']}\n\n{em['body']}"
    parts = []
    for em in thread:
        parts.append(f"From: {em['from']}\nDate: {em['date']}\n\n{em['body']}")
    ctx = "\n\n---\n\n".join(parts)
    if len(ctx) > 8000:
        ctx = "[earlier messages truncated]\n\n" + ctx[-8000:]
    return ctx


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
    mail.append(special_folder(mail, '\\Drafts'), '\\Draft', None, msg.as_bytes())
    mail.logout()

def send_email(to, subject, body, selected_email=None):
    cfg = _cfg()
    msg = build_msg(to, subject, body, selected_email)
    with smtplib.SMTP_SSL(cfg.get('SMTP_SERVER', 'smtp.gmail.com'), 465) as smtp:
        smtp.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
        smtp.sendmail(cfg.get('EMAIL', ''), to, msg.as_bytes())


def find_message(message_id):
    """Look a message up by its Message-ID in Inbox, Sent and Drafts."""
    bare = message_id.strip().strip('<>').replace('"', '')
    cfg = _cfg()
    mail = imaplib.IMAP4_SSL(cfg.get('IMAP_SERVER', 'imap.gmail.com'))
    mail.login(cfg.get('EMAIL', ''), cfg.get('APP_PASSWORD', ''))
    try:
        for folder in ('INBOX', special_folder(mail, '\\Sent'), special_folder(mail, '\\Drafts')):
            if mail.select(folder, readonly=True)[0] != 'OK':
                continue
            _, data = mail.search(None, f'HEADER Message-ID "{bare}"')
            for eid in (data[0].split() if data and data[0] else []):
                _, md = mail.fetch(eid, '(BODY.PEEK[])')
                msg = email.message_from_bytes(md[0][1])
                return {
                    'from':       decode_str(msg['From']),
                    'to':         decode_str(msg['To']),
                    'subject':    decode_str(msg['Subject']),
                    'date':       decode_str(msg['Date']),
                    'body':       get_body(msg),
                    'message_id': (msg.get('Message-ID') or '').strip(),
                    'references': msg.get('References', ''),
                }
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return None


def contact_for(address):
    """(name, notes) for the contact matching `address`, or ('', '')."""
    for c in load_contacts():
        for addr in c.get('emails', []):
            if addr.lower().strip() and addr.lower().strip() in (address or '').lower():
                return c.get('name', ''), c.get('prompt', '')
    return '', ''
