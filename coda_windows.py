"""Windows desktop integration for Coda.

Everything here is per user (HKEY_CURRENT_USER and the user's own folders), so
it needs no administrator rights, and `coda uninstall` removes all of it.

- Right-click "Call Coda" on folders, folder backgrounds and drives.
  (On Windows 11 it appears under "Show more options".)
- Start on login (HKCU Run key).
- A Start menu shortcut.
- The `coda` command (coda.cmd) on the user's PATH.
"""
import os
import subprocess
import winreg

import coda_common as C

CONTEXT_KEYS = {   # registry key → placeholder Explorer fills in with the folder
    r'Software\Classes\Directory\shell\Coda': '%1',
    r'Software\Classes\Directory\Background\shell\Coda': '%V',
    r'Software\Classes\Drive\shell\Coda': '%1',
}
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_VALUE = 'Coda'
ENV_KEY = 'Environment'
ICON_FILE = os.path.join(C.DATA_DIR, 'coda.ico')
START_MENU_LNK = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows',
                              'Start Menu', 'Programs', 'Coda.lnk')
NO_WINDOW = 0x08000000


def _q(path):
    return f'"{path}"'


def tray_command():
    return f'{_q(C.python_bin(gui=True))} {_q(os.path.join(C.CODE_DIR, "coda-tray.py"))}'


# ── Right-click menu ──────────────────────────────────────────────────
def install_context_menu():
    pyw = C.python_bin(gui=True)
    coda_py = os.path.join(C.CODE_DIR, 'coda.py')
    for key, placeholder in CONTEXT_KEYS.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, '', 0, winreg.REG_SZ, 'Call Coda')
            if os.path.exists(ICON_FILE):
                winreg.SetValueEx(k, 'Icon', 0, winreg.REG_SZ, ICON_FILE)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r'\command') as k:
            winreg.SetValueEx(k, '', 0, winreg.REG_SZ,
                              f'{_q(pyw)} {_q(coda_py)} open "{placeholder}"')


def context_menu_installed():
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, next(iter(CONTEXT_KEYS)) + r'\command').Close()
        return True
    except OSError:
        return False


def _delete_tree(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            subs = []
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
        for sub in subs:
            _delete_tree(key + '\\' + sub)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        return True
    except OSError:
        return False


def remove_context_menu():
    return any([_delete_tree(k) for k in CONTEXT_KEYS])


# ── Start on login ────────────────────────────────────────────────────
def set_autostart(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, tray_command())
            return True
        try:
            winreg.DeleteValue(k, RUN_VALUE)
            return True
        except OSError:
            return False


# ── Start menu shortcut ───────────────────────────────────────────────
def _ps_str(s):
    return "'" + s.replace("'", "''") + "'"


def write_start_menu_shortcut():
    os.makedirs(os.path.dirname(START_MENU_LNK), exist_ok=True)
    ps = ('$s = (New-Object -ComObject WScript.Shell).CreateShortcut(' + _ps_str(START_MENU_LNK) + '); '
          '$s.TargetPath = ' + _ps_str(C.python_bin(gui=True)) + '; '
          '$s.Arguments = ' + _ps_str(_q(os.path.join(C.CODE_DIR, 'coda-tray.py'))) + '; '
          '$s.WorkingDirectory = ' + _ps_str(C.HOME) + '; '
          '$s.Description = ' + _ps_str('Open your AI coding agent in any folder') + '; '
          + ('$s.IconLocation = ' + _ps_str(ICON_FILE) + '; ' if os.path.exists(ICON_FILE) else '')
          + '$s.Save()')
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
                           capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def remove_start_menu_shortcut():
    try:
        os.remove(START_MENU_LNK)
        return True
    except OSError:
        return False


# ── The `coda` command on PATH ────────────────────────────────────────
def _broadcast_env_change():
    try:
        import ctypes
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 5000,
                                                 ctypes.byref(res))
    except Exception:
        pass


def _user_path():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ENV_KEY) as k:
            value, kind = winreg.QueryValueEx(k, 'Path')
            return value, kind
    except OSError:
        return '', winreg.REG_EXPAND_SZ


def _same_dir(a, b):
    return os.path.normcase(os.path.normpath(os.path.expandvars(a))) == \
        os.path.normcase(os.path.normpath(b))


def add_to_path(folder):
    """Put `folder` on the user's PATH (new terminals see it). True if changed."""
    value, kind = _user_path()
    parts = [p for p in value.split(';') if p]
    if any(_same_dir(p, folder) for p in parts):
        return False
    parts.append(folder)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ENV_KEY) as k:
        winreg.SetValueEx(k, 'Path', 0, kind if kind in (winreg.REG_SZ, winreg.REG_EXPAND_SZ)
                          else winreg.REG_EXPAND_SZ, ';'.join(parts))
    _broadcast_env_change()
    return True


def remove_from_path(folder):
    value, kind = _user_path()
    parts = [p for p in value.split(';') if p]
    keep = [p for p in parts if not _same_dir(p, folder)]
    if len(keep) == len(parts):
        return False
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ENV_KEY) as k:
        if keep:
            winreg.SetValueEx(k, 'Path', 0, kind, ';'.join(keep))
        else:   # we added the only entry: leave no empty value behind
            winreg.DeleteValue(k, 'Path')
    _broadcast_env_change()
    return True


def on_path(folder):
    value, _ = _user_path()
    return any(_same_dir(p, folder) for p in value.split(';') if p)


# ── Removing Coda's own folder ────────────────────────────────────────
def remove_dir_after_exit(path):
    """Coda's Python runs from inside DATA_DIR, and Windows can't delete a
    program that is running. So a small detached cmd waits a few seconds,
    until we have exited, and then deletes the folder."""
    C.detached_popen(['cmd', '/c', f'ping -n 4 127.0.0.1 >nul & rmdir /s /q "{path}"'],
                     cwd=os.environ.get('TEMP') or C.HOME)
