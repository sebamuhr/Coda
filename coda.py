#!/usr/bin/env python3
"""Coda command-line entry point.

    coda                    start a coding session in the current folder
    coda code [FOLDER]      same, in FOLDER
    coda open [FOLDER]      open a new terminal window with a coding session
    coda tray | email | prefs
    coda mail ...           list / read / draft / send email (for AI agents)
    coda email-model        create the local email model (coda2.0:3b)
    coda doctor             show what is installed where, and any leftovers
    coda integrate          (re)create launcher, autostart, right-click menu
    coda update             update to the latest version
    coda uninstall          remove Coda completely
    coda version
"""
import argparse
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coda_common as C  # noqa: E402

H = C.HOME

# Every file any version of Coda has ever created outside its own folders.
# Uninstall and the legacy cleanup both walk this list, so nothing is left behind.
# CURRENT_* are (re)written by `coda integrate`; LEGACY_* only older versions made.
CURRENT_LINUX = [
    '~/.config/autostart/coda.desktop',
    '~/.local/share/applications/coda.desktop',
    '~/.local/share/icons/coda.png',
    '~/.local/share/nautilus-python/extensions/coda_extension.py',
]
LEGACY_LINUX = [
    '~/.config/autostart/coda-tray.desktop',          # older manual setup
    '~/Desktop/coda.desktop',
    '~/.local/share/icons/coda.svg',
    '~/.local/share/nautilus/python-extensions/coda_extension.py',  # very old path
]
CURRENT_MAC = ['~/Library/LaunchAgents/com.coda.plist', '~/Applications/Coda.app']
LEGACY_MAC = ['~/Library/LaunchAgents/com.coda.ollama.plist']
LINUX_FILES = CURRENT_LINUX + LEGACY_LINUX
MAC_FILES = CURRENT_MAC + LEGACY_MAC
LEGACY_APP_DIRS = ['~/Coda', '~/coda-project']
LEGACY_RUNTIME = ['/tmp/coda-tray.lock', '/tmp/coda-running', '/tmp/coda_terminals']
SHELL_RCS = ['~/.bashrc', '~/.zshrc']


def ex(p):
    return os.path.expanduser(p)


def say(msg=''):
    print(msg, flush=True)


def confirm(question, default=False, assume=None):
    if assume is not None:
        return assume
    if not sys.stdin.isatty():
        return default
    hint = '[Y/n]' if default else '[y/N]'
    ans = input(f'  {question} {hint} ').strip().lower()
    return default if not ans else ans.startswith('y')


def remove_path(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
        return True
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True
    return False


# ── Processes ─────────────────────────────────────────────────────────
def coda_pids():
    """PIDs of running Coda GUI processes (any install location)."""
    out = subprocess.run(['pgrep', '-f', r'coda-(tray|email|preferences)\.py'],
                         capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if p.isdigit() and int(p) != os.getpid()]


def stop_coda(wait=5.0):
    pids = coda_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + wait
    while time.time() < deadline and any(_alive(p) for p in pids):
        time.sleep(0.2)
    for pid in pids:
        if _alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    return pids


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def spawn_gui(script):
    subprocess.Popen([C.python_bin(), os.path.join(C.CODE_DIR, script)],
                     start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── coda code ─────────────────────────────────────────────────────────
def cmd_code(args):
    folder = os.path.abspath(os.path.expanduser(args.folder or os.getcwd()))
    if not os.path.isdir(folder):
        sys.exit(f'coda: not a folder: {folder}')
    cfg = C.load_config()
    engine = args.engine or cfg.get('engine', 'aider')
    if engine not in C.ENGINES:
        sys.exit(f'coda: unknown coding agent "{engine}" (choose from: {", ".join(C.ENGINES)})')
    exe = C.find_engine(engine)
    extra_args, extra_env = [], {}
    if not exe:
        _fail(args, f'coda: {C.ENGINES[engine]["label"]} is not installed — see {C.ENGINES[engine]["url"]}\n'
                    f'      or pick another coding agent in Coda → Preferences.')
    if args.prompt_file:
        try:
            with open(args.prompt_file) as f:
                prompt = f.read()
            os.remove(args.prompt_file)
        except OSError:
            prompt = ''
        if prompt:
            pa = C.agent_prompt_args(engine, prompt)
            if pa is None:
                _fail(args, f'coda: {C.ENGINES[engine]["label"]} can\'t write emails for Coda — choose '
                            f'Claude Code, Codex, Gemini CLI or Cursor Agent in Preferences → Call Coda.')
            extra_args = pa
    if engine == 'aider':
        provider = cfg.get('provider', 'Ollama (local)')
        if provider in C.PROVIDER_ENV and not cfg.get('api_key'):
            _fail(args, f'coda: no {provider} API key set — open Coda → Preferences.')
        extra_args, extra_env = C.aider_invocation(cfg)
    env = dict(os.environ, **extra_env)

    sys.stdout.write(f'\033]0;Coda · {C.session_label(dict(cfg, engine=engine))}\007')
    sys.stdout.flush()
    os.makedirs(C.MARKER_DIR, exist_ok=True)
    marker = os.path.join(C.MARKER_DIR, f'term_{os.getpid()}_{int(time.time())}')
    open(marker, 'w').close()

    child = None

    def _forward(signum, _frame):
        if child and child.poll() is None:
            child.send_signal(signum)
        if signum in (signal.SIGHUP, signal.SIGTERM):
            _cleanup()
            os._exit(0)

    def _cleanup():
        try:
            os.remove(marker)
        except OSError:
            pass

    for s in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(s, _forward)
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # the agent handles Ctrl-C itself
    try:
        child = subprocess.Popen([exe] + extra_args, cwd=folder, env=env)
        child.wait()
    finally:
        _cleanup()
    if args.keep_open:
        # Keep the window open in the project folder, like a normal terminal.
        shell = os.environ.get('SHELL') or '/bin/bash'
        os.chdir(folder)
        os.execvp(shell, [shell, '-i'])


def _fail(args, msg):
    """Exit with a message — but in a window opened from the desktop, keep it
    on screen until the user has read it."""
    print(msg, file=sys.stderr)
    if getattr(args, 'keep_open', False):
        try:
            input('\nPress Enter to close…')
        except EOFError:
            pass
    sys.exit(1)


def cmd_open(args):
    C.open_session_window(args.folder or os.getcwd())


# ── coda mail (for AI agents and scripts) ─────────────────────────────
def _mail():
    import coda_mail
    st = C.email_settings()
    if not (st['EMAIL'] and st['APP_PASSWORD']):
        sys.exit('coda: no email account set up — open Coda → Preferences → Email '
                 '(address + app password), then try again.')
    return coda_mail


def _short(em):
    return {k: em.get(k, '') for k in ('message_id', 'date', 'from', 'to', 'subject')} | (
        {'unread': em['unread']} if 'unread' in em else {})


def _read_body(args):
    if args.body is not None:
        return args.body
    if args.body_file == '-':
        return sys.stdin.read()
    with open(args.body_file) as f:
        return f.read()


def cmd_mail_list(args):
    m = _mail()
    if args.folder == 'inbox':
        ems = m.fetch_inbox(count=args.n)
        if args.unread:
            ems = [e for e in ems if e.get('unread')]
    elif args.folder == 'sent':
        ems = m.fetch_emails('\\Sent', 'ALL', count=args.n)
    else:
        ems = m.fetch_drafts(count=args.n)
    if args.json:
        say(json.dumps([_short(e) for e in ems], indent=2, ensure_ascii=False))
        return
    for e in ems:
        flag = '● ' if e.get('unread') else '  '
        say(f"{flag}{e['date'][:25]:25}  {e['from'][:38]:38}  {e['subject']}")
        say(f"    id: {e['message_id']}")


def cmd_mail_read(args):
    m = _mail()
    em = m.find_message(args.message_id)
    if not em:
        sys.exit(f'coda: no message with id {args.message_id}')
    thread = m.fetch_thread(em) if not args.no_thread else [em]
    name, notes = m.contact_for(em['from'])
    if args.json:
        say(json.dumps({'message': em, 'thread': thread,
                        'contact': {'name': name, 'notes': notes},
                        'you': {'name': C.load_config().get('user_name', ''),
                                'email': C.email_settings()['EMAIL']}},
                       indent=2, ensure_ascii=False))
        return
    say(m.format_thread(thread))
    if notes:
        say(f'\n[Private notes about {name or em["from"]} — use for tone only, never quote]\n{notes}')


def cmd_mail_draft(args, send=False):
    m = _mail()
    body = _read_body(args)
    reply_to = None
    if args.reply_to:
        reply_to = m.find_message(args.reply_to)
        if not reply_to:
            sys.exit(f'coda: no message with id {args.reply_to}')
    to = args.to or (reply_to and email_address(reply_to.get('from', '')))
    subject = args.subject or (reply_to or {}).get('subject', '')
    if not to:
        sys.exit('coda: --to is required for a new email')
    if send:
        if not args.confirm:
            sys.exit('coda: refusing to send without --confirm (save a draft instead with "coda mail draft")')
        m.send_email(to, subject, body, reply_to)
        C.post_email_event({'kind': 'sent', 'to': to})
        say(f'✓ Sent to {to}')
    else:
        m.save_draft(to, subject, body, reply_to)
        C.post_email_event({'kind': 'draft', 'to': to})
        say(f'✓ Draft saved for {to} — it shows in Coda\'s Drafts tab and in your mail app')


def cmd_mail_suggest(args):
    body = _read_body(args)
    if not body.strip():
        sys.exit('coda: the email text is empty')
    if not args.reply_to and not args.to:
        sys.exit('coda: give --reply-to MESSAGE_ID, or --to (and --subject) for a new email')
    C.post_email_event({'kind': 'suggest', 'reply_to': args.reply_to or '',
                        'to': args.to or '', 'subject': args.subject or '', 'body': body})
    say('✓ Put in the Coda Email Agent window. The user reviews it there and sends or saves it.')


def email_address(raw):
    import email.utils
    return email.utils.parseaddr(raw)[1] or raw


def cmd_mail_contacts(args):
    import coda_mail
    cs = coda_mail.load_contacts()
    if args.address:
        name, notes = coda_mail.contact_for(args.address)
        say(json.dumps({'name': name, 'notes': notes}, ensure_ascii=False) if args.json
            else (f'{name}: {notes}' if (name or notes) else 'no contact notes'))
        return
    if args.json:
        say(json.dumps(cs, indent=2, ensure_ascii=False))
        return
    for c in cs:
        say(f"{c.get('name') or '?'}  <{', '.join(c.get('emails', []))}>\n    {c.get('prompt', '')}")


def cmd_mail_check(_args):
    m = _mail()
    import imaplib
    st = C.email_settings()
    try:
        conn = imaplib.IMAP4_SSL(st['IMAP_SERVER'])
        conn.login(st['EMAIL'], st['APP_PASSWORD'])
        sent, drafts = m.special_folder(conn, '\\Sent'), m.special_folder(conn, '\\Drafts')
        conn.logout()
    except Exception as e:
        sys.exit(f'coda: could not log in to {st["IMAP_SERVER"]} as {st["EMAIL"]}: {e}')
    say(f'✓ Logged in to {st["IMAP_SERVER"]} as {st["EMAIL"]}  (sent: {sent}, drafts: {drafts})')


def cmd_email_window(args):
    if not C.load_config().get('email_enabled', True):
        sys.exit('coda: the Email Agent is turned off — turn it on in Preferences → Email')
    spawn_gui('coda-email.py')


# ── coda email-model ──────────────────────────────────────────────────
def cmd_email_model(args):
    cfg = C.load_config()
    host = args.host or cfg.get('email_ollama_ip') or 'localhost'
    try:
        if C.email_model_installed(host) and not args.force:
            say(f'  ✓ {C.EMAIL_MODEL} is already installed on {C.ollama_url(host)}')
            return
        last = ['']

        def progress(msg):
            if msg != last[0]:
                last[0] = msg
                print(f'\r    {msg}      ', end='', flush=True)
        C.install_email_model(host, progress)
        say()
    except Exception as e:
        say()
        sys.exit(f'coda: could not set up the email model on {C.ollama_url(host)}: {e}')


# ── coda integrate ────────────────────────────────────────────────────
def _write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)
    os.chmod(path, mode)


def write_launcher():
    py = C.python_bin()
    _write(C.BIN_LAUNCHER,
           f'#!/bin/sh\n{C.LAUNCHER_TAG} — created by the Coda installer; '
           f'removed by "coda uninstall"\nexec "{py}" "{os.path.join(C.CODE_DIR, "coda.py")}" "$@"\n',
           0o755)


def write_icon_png(path):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False
    S = 256
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, S - 4, S - 4], fill='white', outline='black', width=8)
    r, lw = S * 0.32, int(S / 9)
    d.arc([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r], start=40, end=320, fill='black', width=lw)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return True


def cleanup_legacy(remove_old_copies=None, verbose=True):
    """Remove launchers/aliases/locks left by older Coda versions and stray copies."""
    removed = []
    files = LEGACY_LINUX if C.PLATFORM == 'Linux' else LEGACY_MAC
    for p in files + LEGACY_RUNTIME:
        if remove_path(ex(p)):
            removed.append(p)
    removed += strip_shell_aliases()
    for d in LEGACY_APP_DIRS:
        path = ex(d)
        if not os.path.isdir(path) or os.path.realpath(path) == os.path.realpath(C.CODE_DIR):
            continue
        if C.is_git_checkout(path):
            if verbose:
                say(f'  •  {d} is a git checkout of Coda — left alone (delete it yourself if unused)')
            continue
        if confirm(f'Remove old Coda copy {d}?', default=True, assume=remove_old_copies):
            shutil.rmtree(path)
            removed.append(d)
    if verbose:
        for r in removed:
            say(f'  ✓  removed {r}')
    return removed


def strip_shell_aliases():
    removed = []
    for rc in SHELL_RCS:
        path = ex(rc)
        try:
            with open(path) as f:
                lines = f.readlines()
        except OSError:
            continue
        keep = [l for l in lines if not (
            l.strip() == '# Coda - Local AI coding assistant'
            or l.lstrip().startswith(('alias coda=', 'alias coda-start=')))]
        if len(keep) != len(lines):
            with open(path, 'w') as f:
                f.writelines(keep)
            removed.append(f'{rc} (coda alias — it contained your API key in plain text)')
    return removed


def cmd_integrate(args):
    if not args.no_cleanup:
        cleanup_legacy(remove_old_copies=args.yes or None)
    write_launcher()
    say(f'  ✓  command:     {C.BIN_LAUNCHER}')
    tray = f'"{C.python_bin()}" "{os.path.join(C.CODE_DIR, "coda-tray.py")}"'
    if C.PLATFORM == 'Linux':
        icon = ex('~/.local/share/icons/coda.png')
        write_icon_png(icon)
        desktop = ('[Desktop Entry]\nType=Application\nName=Coda\n'
                   'Comment=Your local AI assistant — code and email\n'
                   f'Exec={tray}\nIcon={icon}\nTerminal=false\n'
                   'Categories=Development;Utility;\nStartupNotify=false\n')
        _write(ex('~/.local/share/applications/coda.desktop'), desktop, 0o755)
        say('  ✓  app launcher entry')
        if not args.no_autostart:
            _write(ex('~/.config/autostart/coda.desktop'),
                   desktop + 'X-GNOME-Autostart-enabled=true\n')
            say('  ✓  start on login')
        ext_dst = ex('~/.local/share/nautilus-python/extensions/coda_extension.py')
        os.makedirs(os.path.dirname(ext_dst), exist_ok=True)
        shutil.copy(os.path.join(C.CODE_DIR, 'coda_extension.py'), ext_dst)
        subprocess.run(['nautilus', '-q'], capture_output=True)
        say('  ✓  right-click "Call Coda" in Files')
        subprocess.run(['update-desktop-database', ex('~/.local/share/applications')],
                       capture_output=True)
    else:
        plist = ex('~/Library/LaunchAgents/com.coda.plist')
        _write(plist, f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.coda.tray</string>
  <key>ProgramArguments</key><array>
    <string>{C.python_bin()}</string><string>{os.path.join(C.CODE_DIR, "coda-tray.py")}</string>
  </array>
  <key>RunAtLoad</key><{"false" if args.no_autostart else "true"}/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardErrorPath</key><string>{H}/.coda-error.log</string>
</dict></plist>
''')
        subprocess.run(['launchctl', 'unload', plist], capture_output=True)
        subprocess.run(['launchctl', 'load', plist], capture_output=True)
        app = ex('~/Applications/Coda.app/Contents')
        _write(os.path.join(app, 'MacOS', 'Coda'),
               '#!/bin/bash\nlaunchctl kickstart "gui/$(id -u)/com.coda.tray" 2>/dev/null '
               f'|| exec {tray}\n', 0o755)
        _write(os.path.join(app, 'Info.plist'), '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Coda</string>
  <key>CFBundleIdentifier</key><string>com.sebamuhr.coda</string>
  <key>CFBundleExecutable</key><string>Coda</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
</dict></plist>
''')
        say('  ✓  login item and ~/Applications/Coda.app')
    C.write_install(C.CODE_DIR, managed=os.path.realpath(C.CODE_DIR) == os.path.realpath(C.MANAGED_APP_DIR))
    path_dirs = os.environ.get('PATH', '').split(os.pathsep)
    if os.path.dirname(C.BIN_LAUNCHER) not in path_dirs:
        say('  ⚠  ~/.local/bin is not on your PATH yet — log out and in, or add it to your shell rc.')


# ── coda doctor ───────────────────────────────────────────────────────
def cmd_doctor(_args):
    inst = C.read_install()
    say(f'Coda {C.VERSION}')
    say(f'  code      : {C.CODE_DIR}' + ('  (git checkout)' if C.is_git_checkout(C.CODE_DIR) else ''))
    say(f'  installed : {inst.get("code_dir", "— (not installed)")}')
    say(f'  config    : {C.CONFIG_FILE}' + ('' if os.path.exists(C.CONFIG_FILE) else '  (missing)'))
    say(f'  python    : {C.python_bin()}')
    cfg = C.load_config()
    eng = cfg.get('engine', 'aider')
    say(f'  agent     : {C.ENGINES.get(eng, {}).get("label", eng)} → {C.find_engine(eng) or "NOT FOUND"}')
    say(f'  available : {", ".join(C.ENGINES[e]["label"] for e in C.installed_engines()) or "none"}')
    say(f'  command   : {C.BIN_LAUNCHER if os.path.exists(C.BIN_LAUNCHER) else "not installed"}')
    pids = coda_pids()
    say(f'  running   : {", ".join(map(str, pids)) if pids else "no"}')
    problems = []
    if inst.get('code_dir') and os.path.realpath(inst['code_dir']) != os.path.realpath(C.CODE_DIR):
        problems.append(f'this copy ({C.CODE_DIR}) is not the installed one ({inst["code_dir"]})')
    for d in LEGACY_APP_DIRS:
        if os.path.isdir(ex(d)) and os.path.realpath(ex(d)) != os.path.realpath(C.CODE_DIR):
            problems.append(f'extra copy of Coda at {d}')
    for p in (LEGACY_LINUX if C.PLATFORM == 'Linux' else LEGACY_MAC):
        if os.path.exists(ex(p)):
            problems.append(f'leftover from an old version: {p}')
    for rc in SHELL_RCS:
        try:
            if any(l.lstrip().startswith('alias coda=') for l in open(ex(rc))):
                problems.append(f'old "coda" alias in {rc} (stores your API key in plain text)')
        except OSError:
            pass
    for p in LEGACY_RUNTIME:
        if os.path.exists(p):
            problems.append(f'stale lock/marker from an old version: {p}')
    if problems:
        say('\nProblems:')
        for p in problems:
            say(f'  ✗  {p}')
        say('\nFix with:  coda integrate   (removes leftovers and duplicates)')
    else:
        say('\n✓ No problems found.')


# ── coda update ───────────────────────────────────────────────────────
def cmd_update(args):
    if C.is_git_checkout(C.CODE_DIR):
        r = subprocess.run(['git', 'pull', '--ff-only'], cwd=C.CODE_DIR,
                           capture_output=True, text=True)
        say((r.stdout + r.stderr).strip())
        if r.returncode:
            sys.exit(1)
    else:
        url = f'https://github.com/{C.REPO}/archive/refs/heads/{args.branch}.tar.gz'
        say(f'Downloading {url} …')
        tmp = tempfile.mkdtemp(prefix='coda-update-')
        try:
            tgz = os.path.join(tmp, 'coda.tar.gz')
            urllib.request.urlretrieve(url, tgz)
            with tarfile.open(tgz) as t:
                t.extractall(tmp, filter='data')
            src = next(p for p in glob.glob(os.path.join(tmp, '*')) if os.path.isdir(p))
            if not os.path.exists(os.path.join(src, 'coda.py')):
                sys.exit('coda: download does not look like Coda — update aborted')
            old = C.CODE_DIR + '.old'
            shutil.rmtree(old, ignore_errors=True)
            os.rename(C.CODE_DIR, old)
            shutil.move(src, C.CODE_DIR)
            shutil.rmtree(old, ignore_errors=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # Re-run integration from the *new* code, then restart the tray.
    subprocess.run(C.coda_command() + ['integrate', '--no-cleanup'], check=False)
    if args.restart and stop_coda():
        spawn_gui('coda-tray.py')
    say('✓ Coda is up to date.')


# ── coda uninstall ────────────────────────────────────────────────────
def cmd_uninstall(args):
    yes = True if args.yes else None
    say('Uninstalling Coda…')
    stopped = stop_coda()
    if stopped:
        say(f'  ✓  stopped running Coda ({len(stopped)} process{"es" if len(stopped) != 1 else ""})')

    cfg = C.load_config()
    if not args.keep_model and confirm(
            f'Remove the {C.EMAIL_MODEL} email model from Ollama?', default=True, assume=yes):
        try:
            C.remove_email_model(cfg.get('email_ollama_ip') or 'localhost')
            say(f'  ✓  removed {C.EMAIL_MODEL}')
        except Exception:
            say(f'  •  {C.EMAIL_MODEL} not removed (Ollama not reachable or model absent)')

    for p in (LINUX_FILES if C.PLATFORM == 'Linux' else MAC_FILES):
        if C.PLATFORM == 'Darwin' and p.endswith('.plist'):
            subprocess.run(['launchctl', 'unload', ex(p)], capture_output=True)
        if remove_path(ex(p)):
            say(f'  ✓  removed {p}')
    if C.PLATFORM == 'Linux':
        subprocess.run(['nautilus', '-q'], capture_output=True)
    for r in strip_shell_aliases():
        say(f'  ✓  cleaned {r}')
    try:
        if C.LAUNCHER_TAG in open(C.BIN_LAUNCHER).read():
            os.remove(C.BIN_LAUNCHER)
            say('  ✓  removed ~/.local/bin/coda')
    except OSError:
        pass

    if not args.keep_config and confirm(
            'Remove your settings and contacts (~/.config/coda)?', default=True, assume=yes):
        if remove_path(C.CONFIG_DIR):
            say('  ✓  removed ~/.config/coda')

    legacy_aider = ex('~/aider-env')
    if os.path.isdir(legacy_aider) and confirm(
            'Remove ~/aider-env (the coding engine from older Coda versions)?',
            default=True, assume=yes):
        shutil.rmtree(legacy_aider)
        say('  ✓  removed ~/aider-env')

    for p in LEGACY_RUNTIME + [C.RUNTIME_DIR]:
        remove_path(p)

    for d in LEGACY_APP_DIRS:
        path = ex(d)
        if os.path.isdir(path) and not C.is_git_checkout(path):
            shutil.rmtree(path)
            say(f'  ✓  removed {d}')

    # The data dir holds the venvs and (for normal installs) the app itself.
    # A developer's git checkout is never deleted.
    code_is_managed = os.path.realpath(C.CODE_DIR).startswith(os.path.realpath(C.DATA_DIR) + os.sep)
    if remove_path(C.DATA_DIR):
        say('  ✓  removed ~/.local/share/coda')
    kept = [d for d in [C.CODE_DIR] + [ex(x) for x in LEGACY_APP_DIRS]
            if not code_is_managed or d != C.CODE_DIR]
    for d in kept:
        if os.path.isdir(d) and C.is_git_checkout(d):
            say(f'  •  kept your git checkout {d} — delete it yourself if you no longer need it')
    say('\n✓ Coda has been uninstalled.')


def main():
    ap = argparse.ArgumentParser(prog='coda', description='Coda — your local AI assistant')
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('code', help='coding session in this terminal')
    p.add_argument('folder', nargs='?')
    p.add_argument('--engine', help='coding agent for this session: ' + ', '.join(C.ENGINES))
    p.add_argument('--keep-open', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--prompt-file', help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_code)
    p = sub.add_parser('open', help='coding session in a new terminal window')
    p.add_argument('folder', nargs='?')
    p.set_defaults(fn=cmd_open)
    for name, script in (('tray', 'coda-tray.py'), ('email', 'coda-email.py'),
                         ('prefs', 'coda-preferences.py')):
        sub.add_parser(name, help=f'start {script}').set_defaults(fn=lambda a, s=script: spawn_gui(s))
    sub.choices['email'].set_defaults(fn=cmd_email_window)
    p = sub.add_parser('email-model', help=f'install {C.EMAIL_MODEL} on Ollama')
    p.add_argument('--host')
    p.add_argument('--force', action='store_true')
    p.set_defaults(fn=cmd_email_model)
    p = sub.add_parser('integrate', help='create launcher, autostart and right-click menu')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--no-autostart', action='store_true')
    p.add_argument('--no-cleanup', action='store_true')
    p.set_defaults(fn=cmd_integrate)
    mp = sub.add_parser('mail', help='read email and write drafts (for AI agents)')
    ms = mp.add_subparsers(dest='mail_cmd', required=True)
    p = ms.add_parser('check', help='test the email login')
    p.set_defaults(fn=cmd_mail_check)
    p = ms.add_parser('list', help='list recent messages')
    p.add_argument('--folder', choices=['inbox', 'sent', 'drafts'], default='inbox')
    p.add_argument('--unread', action='store_true')
    p.add_argument('-n', type=int, default=15)
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_mail_list)
    p = ms.add_parser('read', help='show a message with its whole thread')
    p.add_argument('message_id')
    p.add_argument('--no-thread', action='store_true')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_mail_read)
    for name, send in (('draft', False), ('send', True)):
        p = ms.add_parser(name, help='save a draft (safe)' if not send else 'send immediately (needs --confirm)')
        p.add_argument('--to')
        p.add_argument('--subject')
        p.add_argument('--reply-to', metavar='MESSAGE_ID')
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument('--body')
        g.add_argument('--body-file', metavar='PATH|-')
        if send:
            p.add_argument('--confirm', action='store_true')
        p.set_defaults(fn=lambda a, s=send: cmd_mail_draft(a, send=s))
    p = ms.add_parser('suggest', help='put an email text in the Email Agent window for review')
    p.add_argument('--to')
    p.add_argument('--subject')
    p.add_argument('--reply-to', metavar='MESSAGE_ID')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--body')
    g.add_argument('--body-file', metavar='PATH|-')
    p.set_defaults(fn=cmd_mail_suggest)
    p = ms.add_parser('contacts', help='your per-contact tone notes')
    p.add_argument('address', nargs='?')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_mail_contacts)
    sub.add_parser('doctor', help='check the installation').set_defaults(fn=cmd_doctor)
    p = sub.add_parser('update', help='update Coda')
    p.add_argument('--branch', default='main')
    p.add_argument('--no-restart', dest='restart', action='store_false')
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser('uninstall', help='remove Coda completely')
    p.add_argument('--yes', action='store_true', help='do not ask')
    p.add_argument('--keep-config', action='store_true')
    p.add_argument('--keep-model', action='store_true')
    p.set_defaults(fn=cmd_uninstall)
    sub.add_parser('version').set_defaults(fn=lambda a: say(f'Coda {C.VERSION}'))
    args = ap.parse_args()
    if not args.cmd:
        args = ap.parse_args(['code'])
    args.fn(args)


if __name__ == '__main__':
    main()
