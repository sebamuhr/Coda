#!/usr/bin/env python3
"""Coda command-line entry point.

    coda                    start a coding session in the current folder
    coda code [FOLDER]      same, in FOLDER
    coda open [FOLDER]      open a new terminal window with a coding session
    coda tray | prefs       start the tray icon / Preferences
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
GUI_PATTERN = r'coda-(tray|email|preferences)\.py'


def coda_pids():
    """PIDs of running Coda GUI processes (any install location).

    Only Python processes count: a shell or an editor whose command line
    merely mentions coda-tray.py must never be stopped."""
    if C.WINDOWS:
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' "
              "-and $_.CommandLine -match '" + GUI_PATTERN + "' } | ForEach-Object { $_.ProcessId }")
        try:
            out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                                 capture_output=True, text=True, timeout=30,
                                 creationflags=0x08000000).stdout.split()
        except (OSError, subprocess.TimeoutExpired):
            out = []
        pids = [int(p) for p in out if p.isdigit()]
    else:
        out = subprocess.run(['pgrep', '-f', GUI_PATTERN],
                             capture_output=True, text=True).stdout.split()
        pids = []
        for p in out:
            if not p.isdigit():
                continue
            comm = subprocess.run(['ps', '-o', 'comm=', '-p', p],
                                  capture_output=True, text=True).stdout.strip()
            if 'python' in os.path.basename(comm).lower():
                pids.append(int(p))
    # Never ourselves, nor a Preferences window that started us (`coda update`).
    me = {os.getpid()}
    if os.environ.get('CODA_CALLER_PID', '').isdigit():
        me.add(int(os.environ['CODA_CALLER_PID']))
    return [p for p in pids if p not in me]


def stop_coda(wait=5.0):
    pids = coda_pids()
    for pid in pids:
        C.terminate(pid, tree=False)   # not the tree: open coding sessions stay open
    deadline = time.time() + wait
    while time.time() < deadline and any(C.pid_alive(p) for p in pids):
        time.sleep(0.2)
    for pid in pids:
        if C.pid_alive(pid):
            C.terminate(pid, tree=False, force=True)
    return pids


def spawn_gui(script):
    C.detached_popen([C.python_bin(gui=True), os.path.join(C.CODE_DIR, script)])


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
    if engine == 'aider':
        provider = cfg.get('provider', 'Ollama (local)')
        if provider in C.PROVIDER_ENV and not cfg.get('api_key'):
            _fail(args, f'coda: no {provider} API key set — open Coda → Preferences.')
        extra_args, extra_env = C.aider_invocation(cfg)
    env = dict(os.environ, **extra_env)

    title = f'Coda · {C.session_label(dict(cfg, engine=engine))}'
    if C.WINDOWS:
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass
    else:
        sys.stdout.write(f'\033]0;{title}\007')
        sys.stdout.flush()
    os.makedirs(C.MARKER_DIR, exist_ok=True)
    marker = os.path.join(C.MARKER_DIR, f'term_{os.getpid()}_{int(time.time())}')
    open(marker, 'w').close()

    child = None

    def _forward(signum, _frame):
        if child and child.poll() is None:
            child.send_signal(signum)
        if signum != signal.SIGINT:
            _cleanup()
            os._exit(0)

    def _cleanup():
        try:
            os.remove(marker)
        except OSError:
            pass

    for name in ('SIGHUP', 'SIGTERM'):   # Windows has no SIGHUP
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _forward)
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # the agent handles Ctrl-C itself
    try:
        child = subprocess.Popen([exe] + extra_args, cwd=folder, env=env)
        child.wait()
    finally:
        _cleanup()
    if args.keep_open:
        # Keep the window open in the project folder, like a normal terminal.
        os.chdir(folder)
        if C.WINDOWS:
            shell = shutil.which('pwsh') or shutil.which('powershell')
            sys.exit(subprocess.call([shell, '-NoLogo'] if shell else
                                     [os.environ.get('COMSPEC', 'cmd.exe')]))
        shell = os.environ.get('SHELL') or '/bin/bash'
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


def _write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)
    os.chmod(path, mode)


def write_launcher():
    py = C.python_bin()
    if C.WINDOWS:
        # cmd.exe reads .cmd files in the console code page, so a user name
        # like "José" would break a literal path. Environment variables don't.
        def winpath(p):
            for var in ('LOCALAPPDATA', 'APPDATA', 'USERPROFILE'):
                base = os.environ.get(var)
                if base and os.path.normcase(p).startswith(os.path.normcase(base) + os.sep):
                    return f'%{var}%' + p[len(base):]
            return p
        os.makedirs(C.BIN_DIR, exist_ok=True)
        with open(C.BIN_LAUNCHER, 'w', newline='\r\n', encoding='ascii', errors='replace') as f:
            f.write(f'@echo off\nrem {C.LAUNCHER_TAG} - created by the Coda installer; '
                    f'removed by "coda uninstall"\n'
                    f'"{winpath(py)}" "{winpath(os.path.join(C.CODE_DIR, "coda.py"))}" %*\n')
        return
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
    if path.lower().endswith('.ico'):
        img.save(path, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    else:
        img.save(path)
    return True


def cleanup_email_leftovers():
    """The Email Agent was removed: drop its settings (mail password!),
    contacts and working folder."""
    removed = []
    if os.path.exists(C.CONFIG_FILE):
        try:
            raw = json.load(open(C.CONFIG_FILE))
        except (OSError, ValueError):
            raw = {}
        if any(k in raw for k in C.LEGACY_CONFIG_KEYS):
            C.save_config(C.load_config())
            removed.append('email settings in ~/.config/coda/config.json')
    for f in C.LEGACY_CONFIG_FILES:
        if remove_path(f):
            removed.append(f.replace(H, '~'))
    if remove_path(os.path.join(C.DATA_DIR, 'email-desk')):
        removed.append('~/.local/share/coda/email-desk')
    return removed


def cleanup_legacy(remove_old_copies=None, verbose=True):
    """Remove launchers/aliases/locks left by older Coda versions and stray copies."""
    removed = []
    files = LEGACY_LINUX if C.PLATFORM == 'Linux' else LEGACY_MAC if C.PLATFORM == 'Darwin' else []
    for p in files + LEGACY_RUNTIME:
        if remove_path(ex(p)):
            removed.append(p)
    removed += strip_shell_aliases()
    removed += cleanup_email_leftovers()
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
    else:
        for r in cleanup_email_leftovers():
            say(f'  ✓  removed {r}')
    write_launcher()
    say(f'  ✓  command:     {C.BIN_LAUNCHER}')
    tray = f'"{C.python_bin()}" "{os.path.join(C.CODE_DIR, "coda-tray.py")}"'
    if C.WINDOWS:
        import coda_windows as W
        write_icon_png(W.ICON_FILE)
        W.install_context_menu()
        say('  ✓  right-click "Call Coda" on folders (Windows 11: under "Show more options")')
        W.set_autostart(not args.no_autostart)
        if not args.no_autostart:
            say('  ✓  start on login')
        if W.write_start_menu_shortcut():
            say('  ✓  Start menu shortcut')
        if W.add_to_path(C.BIN_DIR):
            say('  ✓  added the coda command to your PATH (open a new terminal to use it)')
    elif C.PLATFORM == 'Linux':
        icon = ex('~/.local/share/icons/coda.png')
        write_icon_png(icon)
        desktop = ('[Desktop Entry]\nType=Application\nName=Coda\n'
                   'Comment=Open your AI coding agent in any folder\n'
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
    if not C.WINDOWS and C.BIN_DIR not in path_dirs:
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
    for p in (LEGACY_LINUX if C.PLATFORM == 'Linux' else LEGACY_MAC if C.PLATFORM == 'Darwin' else []):
        if os.path.exists(ex(p)):
            problems.append(f'leftover from an old version: {p}')
    if C.WINDOWS and inst.get('code_dir'):
        import coda_windows as W
        if not W.context_menu_installed():
            problems.append('the right-click "Call Coda" entry is missing')
        if not W.on_path(C.BIN_DIR):
            problems.append('the coda command is not on your PATH')
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
            if C.WINDOWS:   # Windows can't rename a folder that a running program uses
                stop_coda()
            old = C.CODE_DIR + '.old'
            shutil.rmtree(old, ignore_errors=True)
            os.rename(C.CODE_DIR, old)
            shutil.move(src, C.CODE_DIR)
            shutil.rmtree(old, ignore_errors=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # Re-run integration from the *new* code, then restart the tray.
    subprocess.run(C.coda_command() + ['integrate', '--no-cleanup'], check=False)
    if args.restart and (stop_coda() or C.WINDOWS):
        spawn_gui('coda-tray.py')
    say('✓ Coda is up to date.')


# ── coda uninstall ────────────────────────────────────────────────────
def cmd_uninstall(args):
    yes = True if args.yes else None
    say('Uninstalling Coda…')
    stopped = stop_coda()
    if stopped:
        say(f'  ✓  stopped running Coda ({len(stopped)} process{"es" if len(stopped) != 1 else ""})')

    if C.WINDOWS:
        import coda_windows as W
        if W.remove_context_menu():
            say('  ✓  removed the right-click "Call Coda" entry')
        if W.set_autostart(False):
            say('  ✓  removed start on login')
        if W.remove_start_menu_shortcut():
            say('  ✓  removed the Start menu shortcut')
        if W.remove_from_path(C.BIN_DIR):
            say('  ✓  removed the coda command from your PATH')
    for p in (LINUX_FILES if C.PLATFORM == 'Linux' else MAC_FILES if C.PLATFORM == 'Darwin' else []):
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
            say(f'  ✓  removed {C.BIN_LAUNCHER.replace(H, "~")}')
    except OSError:
        pass

    if not args.keep_config and confirm(
            f'Remove your settings ({C.CONFIG_DIR.replace(H, "~")})?', default=True, assume=yes):
        if remove_path(C.CONFIG_DIR):
            say(f'  ✓  removed {C.CONFIG_DIR.replace(H, "~")}')

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
    if C.WINDOWS and os.path.isdir(C.DATA_DIR):
        # We are running from inside it; it is deleted a few seconds after we exit.
        import coda_windows as W
        W.remove_dir_after_exit(C.DATA_DIR)
        say(f'  ✓  removing {C.DATA_DIR.replace(H, "~")} (finishes a few seconds after this window closes)')
    elif remove_path(C.DATA_DIR):
        say(f'  ✓  removed {C.DATA_DIR.replace(H, "~")}')
    kept = [d for d in [C.CODE_DIR] + [ex(x) for x in LEGACY_APP_DIRS]
            if not code_is_managed or d != C.CODE_DIR]
    for d in kept:
        if os.path.isdir(d) and C.is_git_checkout(d):
            say(f'  •  kept your git checkout {d} — delete it yourself if you no longer need it')
    say('\n✓ Coda has been uninstalled.')


def main():
    if C.WINDOWS:
        # Windows pipes use an old code page that has no ✓; never crash on it.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(errors='replace')
            except (AttributeError, ValueError):
                pass
    ap = argparse.ArgumentParser(prog='coda', description='Coda — open your AI coding agent in any folder')
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('code', help='coding session in this terminal')
    p.add_argument('folder', nargs='?')
    p.add_argument('--engine', help='coding agent for this session: ' + ', '.join(C.ENGINES))
    p.add_argument('--keep-open', action='store_true', help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_code)
    p = sub.add_parser('open', help='coding session in a new terminal window')
    p.add_argument('folder', nargs='?')
    p.set_defaults(fn=cmd_open)
    for name, script in (('tray', 'coda-tray.py'), ('prefs', 'coda-preferences.py')):
        sub.add_parser(name, help=f'start {script}').set_defaults(fn=lambda a, s=script: spawn_gui(s))
    p = sub.add_parser('integrate', help='create launcher, autostart and right-click menu')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--no-autostart', action='store_true')
    p.add_argument('--no-cleanup', action='store_true')
    p.set_defaults(fn=cmd_integrate)
    sub.add_parser('doctor', help='check the installation').set_defaults(fn=cmd_doctor)
    p = sub.add_parser('update', help='update Coda')
    p.add_argument('--branch', default='main')
    p.add_argument('--no-restart', dest='restart', action='store_false')
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser('uninstall', help='remove Coda completely')
    p.add_argument('--yes', action='store_true', help='do not ask')
    p.add_argument('--keep-config', action='store_true')
    p.set_defaults(fn=cmd_uninstall)
    sub.add_parser('version').set_defaults(fn=lambda a: say(f'Coda {C.VERSION}'))
    args = ap.parse_args()
    if not args.cmd:
        args = ap.parse_args(['code'])
    args.fn(args)


if __name__ == '__main__':
    main()
