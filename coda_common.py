"""Shared paths, config and helpers for every part of Coda.

Everything that needs to know *where* Coda lives, *how* it is configured or
*how* to start a coding session goes through this module, so the tray, the
Preferences window, the right-click extension, the installer and the
uninstaller can never disagree with each other again.
"""
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request

VERSION  = '2.0.0'
REPO     = 'sebamuhr/Coda'
PLATFORM = platform.system()          # 'Linux' or 'Darwin'
HOME     = os.path.expanduser('~')

# ── Paths ─────────────────────────────────────────────────────────────
# Code     : wherever coda.py lives (a managed copy in DATA_DIR/app, or a
#            git checkout for developers).
# Config   : settings, contacts, window size — the user's data.
# Data     : everything the installer creates (venvs, managed app copy).
# Runtime  : lock + session markers; per-user and wiped on reboot.
CODE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR  = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.join(HOME, '.config'), 'coda')
DATA_DIR    = os.path.join(os.environ.get('XDG_DATA_HOME') or os.path.join(HOME, '.local', 'share'), 'coda')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
LEGACY_EMAIL_CONF = os.path.join(CONFIG_DIR, 'email.conf')
INSTALL_FILE = os.path.join(DATA_DIR, 'install.json')
MANAGED_APP_DIR = os.path.join(DATA_DIR, 'app')
VENV_DIR    = os.path.join(DATA_DIR, 'venv')
AIDER_ENV   = os.path.join(DATA_DIR, 'aider-env')
BIN_LAUNCHER = os.path.join(HOME, '.local', 'bin', 'coda')
LAUNCHER_TAG = '# coda-launcher'   # marks ~/.local/bin/coda as ours

_rt = os.environ.get('XDG_RUNTIME_DIR')
RUNTIME_DIR = os.path.join(_rt, 'coda') if _rt and os.path.isdir(_rt) \
    else os.path.join(tempfile.gettempdir(), f'coda-{os.getuid()}')
LOCK_FILE    = os.path.join(RUNTIME_DIR, 'tray.lock')
RUNNING_FILE = os.path.join(RUNTIME_DIR, 'running')
MARKER_DIR   = os.path.join(RUNTIME_DIR, 'sessions')   # one file per coding session

EMAIL_MODEL      = 'coda2.0:3b'
EMAIL_BASE_MODEL = 'qwen2.5:3b'
EMAIL_SYSTEM = ('You write emails on behalf of the user. Write naturally and concisely '
                'in their voice. Do not use robotic phrases or unnecessary pleasantries.')

PROVIDERS = ['Ollama (local)', 'Gemini', 'OpenAI', 'Claude']
PROVIDER_MODELS = {
    'Ollama (local)': ['qwen2.5-coder:7b', 'qwen2.5-coder:3b'],
    'Gemini':         ['gemini-2.5-flash', 'gemini-2.5-pro'],
    'OpenAI':         ['gpt-4o', 'gpt-4o-mini'],
    'Claude':         ['claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-5-5'],
}
PROVIDER_ENV = {'Gemini': 'GEMINI_API_KEY', 'OpenAI': 'OPENAI_API_KEY', 'Claude': 'ANTHROPIC_API_KEY'}

# Which coding agent "Call Coda" opens. Everything except aider brings its
# own login and model choice, so Coda only passes the folder.
ENGINES = {
    'claude':       {'label': 'Claude Code',  'cmd': 'claude',       'url': 'https://claude.com/claude-code'},
    'codex':        {'label': 'Codex CLI',    'cmd': 'codex',        'url': 'https://github.com/openai/codex'},
    'cursor-agent': {'label': 'Cursor Agent', 'cmd': 'cursor-agent', 'url': 'https://cursor.com/cli'},
    'gemini':       {'label': 'Gemini CLI',   'cmd': 'gemini',       'url': 'https://github.com/google-gemini/gemini-cli'},
    'aider':        {'label': 'Aider',        'cmd': 'aider',        'url': 'https://aider.chat'},
}

DEFAULT_CONFIG = {
    'engine':           'aider',
    'provider':         'Ollama (local)',
    'ollama_ip':        'localhost',
    'model':            '',
    'api_key':          '',
    'email_provider':   'Gmail',
    'email':            '',
    'app_password':     '',
    'imap_server':      'imap.gmail.com',
    'smtp_server':      'smtp.gmail.com',
    'refresh_minutes':  5,
    'email_sync_count': 15,
    'user_name':        '',
    'theme':            'light',
    'email_ollama_ip':  'localhost',
}


def ensure_private_dir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)


# ── Config ────────────────────────────────────────────────────────────
def _read_legacy_email_conf():
    out = {}
    try:
        with open(LEGACY_EMAIL_CONF) as f:
            for line in f:
                if '=' in line:
                    k, v = line.rstrip('\n').split('=', 1)
                    out[k] = v
    except OSError:
        pass
    mapping = {'EMAIL': 'email', 'APP_PASSWORD': 'app_password', 'IMAP_SERVER': 'imap_server',
               'SMTP_SERVER': 'smtp_server', 'PROVIDER': 'email_provider',
               'EMAIL_OLLAMA_IP': 'email_ollama_ip', 'USER_NAME': 'user_name', 'THEME': 'theme'}
    return {mapping[k]: v for k, v in out.items() if k in mapping and v}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    # Older versions kept email settings in a second file; fold them in.
    for k, v in _read_legacy_email_conf().items():
        if not cfg.get(k) or cfg.get(k) == DEFAULT_CONFIG.get(k):
            cfg[k] = v
    return cfg


def save_config(cfg):
    """Atomic write, readable only by the user (it holds API keys/passwords)."""
    ensure_private_dir(CONFIG_DIR)
    tmp = CONFIG_FILE + '.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)
    try:
        os.remove(LEGACY_EMAIL_CONF)   # now merged into config.json
    except OSError:
        pass


def email_settings():
    """Email settings in the key format coda-email.py uses."""
    c = load_config()
    return {
        'EMAIL':           c.get('email', ''),
        'APP_PASSWORD':    c.get('app_password', ''),
        'IMAP_SERVER':     c.get('imap_server') or 'imap.gmail.com',
        'SMTP_SERVER':     c.get('smtp_server') or 'smtp.gmail.com',
        'SYNC_COUNT':      str(c.get('email_sync_count', 15)),
        'THEME':           c.get('theme', 'light'),
        'EMAIL_OLLAMA_IP': c.get('email_ollama_ip') or 'localhost',
        'USER_NAME':       c.get('user_name', ''),
    }


def normalize_host(raw):
    """Accept an IP, hostname or URL — return just the host."""
    h = (raw or '').strip().replace('https://', '').replace('http://', '')
    return h.split('/')[0].split(':')[0] or 'localhost'


def ollama_url(host):
    return f'http://{normalize_host(host)}:11434'


# ── Install state ─────────────────────────────────────────────────────
def read_install():
    try:
        with open(INSTALL_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_install(code_dir, managed):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INSTALL_FILE, 'w') as f:
        json.dump({'version': VERSION, 'code_dir': code_dir, 'managed': managed}, f, indent=2)


def is_git_checkout(path):
    return os.path.isdir(os.path.join(path, '.git'))


def python_bin():
    """The interpreter Coda's GUI parts run with."""
    venv_py = os.path.join(VENV_DIR, 'bin', 'python3')
    return venv_py if os.access(venv_py, os.X_OK) else (shutil.which('python3') or '/usr/bin/python3')


def coda_command():
    """argv prefix that runs the Coda CLI."""
    if os.access(BIN_LAUNCHER, os.X_OK):
        return [BIN_LAUNCHER]
    return [python_bin(), os.path.join(CODE_DIR, 'coda.py')]


# ── Coding sessions (aider) ───────────────────────────────────────────
def find_aider(cfg=None):
    cfg = cfg or load_config()
    for env in (cfg.get('aider_env'), AIDER_ENV, os.path.join(HOME, 'aider-env')):
        if env:
            exe = os.path.join(env, 'bin', 'aider')
            if os.access(exe, os.X_OK):
                return exe
    return shutil.which('aider')


def find_engine(name):
    """Path to an agent CLI. Desktop launches often have a shorter PATH than
    your terminal, so common install dirs and a login shell are tried too."""
    if name == 'aider':
        return find_aider()
    cmd = ENGINES.get(name, {}).get('cmd', name)
    exe = shutil.which(cmd)
    if exe:
        return exe
    for d in ('~/.local/bin', '~/.npm-global/bin', '~/.bun/bin', '~/.cargo/bin',
              '/usr/local/bin', '/opt/homebrew/bin', '~/.claude/local'):
        p = os.path.join(os.path.expanduser(d), cmd)
        if os.access(p, os.X_OK):
            return p
    shell = os.environ.get('SHELL') or '/bin/bash'
    try:
        out = subprocess.run([shell, '-lic', f'command -v {cmd}'], capture_output=True,
                             text=True, timeout=5, stdin=subprocess.DEVNULL).stdout.strip().splitlines()
        if out and os.access(out[-1], os.X_OK):
            return out[-1]
    except Exception:
        pass
    return None


def installed_engines():
    return [k for k in ENGINES if find_engine(k)]


def session_label(cfg):
    engine = cfg.get('engine', 'aider')
    if engine == 'aider':
        return cfg.get('provider', 'Ollama (local)')
    return ENGINES.get(engine, {}).get('label', engine)


def aider_invocation(cfg):
    """Return (argv-after-aider, extra-env). Keys go in the env, never on a command line."""
    provider = cfg.get('provider', 'Ollama (local)')
    model    = (cfg.get('model') or '').strip()
    env = {}
    if provider == 'Gemini':
        env['GEMINI_API_KEY'] = cfg.get('api_key', '')
        model_arg = f"gemini/{model or PROVIDER_MODELS['Gemini'][0]}"
    elif provider == 'OpenAI':
        env['OPENAI_API_KEY'] = cfg.get('api_key', '')
        model_arg = f"openai/{model or PROVIDER_MODELS['OpenAI'][0]}"
    elif provider == 'Claude':
        env['ANTHROPIC_API_KEY'] = cfg.get('api_key', '')
        model_arg = f"anthropic/{model or PROVIDER_MODELS['Claude'][0]}"
    else:
        env['OLLAMA_API_BASE'] = ollama_url(cfg.get('ollama_ip'))
        model_arg = f"ollama_chat/{model or PROVIDER_MODELS['Ollama (local)'][0]}"
    return ['--model', model_arg], env


def live_sessions():
    """Session marker files whose process is still alive; prunes dead ones."""
    alive = []
    try:
        names = os.listdir(MARKER_DIR)
    except OSError:
        return alive
    for name in names:
        path = os.path.join(MARKER_DIR, name)
        try:
            pid = int(name.split('_')[1])
            os.kill(pid, 0)
            alive.append((pid, path))
        except (IndexError, ValueError, ProcessLookupError):
            try:
                os.remove(path)
            except OSError:
                pass
        except PermissionError:
            alive.append((pid, path))
    return alive


def open_session_window(folder):
    """Open a new terminal window running a Coda coding session in `folder`."""
    folder = os.path.abspath(os.path.expanduser(folder))
    title = f'Coda · {session_label(load_config())}'
    argv = coda_command() + ['code', '--keep-open', folder]
    if PLATFORM == 'Darwin':
        import shlex
        line = ' '.join(shlex.quote(a) for a in argv)
        line = line.replace('\\', '\\\\').replace('"', '\\"')
        subprocess.Popen(['osascript', '-e', f'tell application "Terminal" to do script "{line}"',
                          '-e', 'tell application "Terminal" to activate'])
        return
    for term in (['gnome-terminal', f'--title={title}', '--'],
                 ['kgx', f'--title={title}', '--'],
                 ['konsole', '-p', f'tabtitle={title}', '-e'],
                 ['xfce4-terminal', f'--title={title}', '-x'],
                 ['x-terminal-emulator', '-T', title, '-e'],
                 ['xterm', '-T', title, '-e']):
        if shutil.which(term[0]):
            subprocess.Popen(term + argv, start_new_session=True)
            return
    raise RuntimeError('No terminal emulator found (tried gnome-terminal, konsole, xterm…)')


# ── Email model (Ollama) ──────────────────────────────────────────────
def _ollama_json(base, path, payload=None, method=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def ollama_models(host):
    with _ollama_json(ollama_url(host), '/api/tags', timeout=5) as r:
        return [m.get('name', '') for m in json.loads(r.read()).get('models', [])]


def email_model_installed(host):
    return any(n.startswith(EMAIL_MODEL) for n in ollama_models(host))


def _stream(resp, progress=None, label=''):
    for line in resp:
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get('error'):
            raise RuntimeError(obj['error'])
        if progress and obj.get('total') and obj.get('completed'):
            progress(f"{label} {int(obj['completed'] / obj['total'] * 100)}%")


def install_email_model(host, progress=print):
    """Create coda2.0:3b on the Ollama server at `host`.

    The base model is only removed afterwards if *we* downloaded it, so a
    user's own copy of qwen2.5:3b is never deleted.
    """
    base = ollama_url(host)
    had_base = any(n.startswith(EMAIL_BASE_MODEL) for n in ollama_models(host))
    if not had_base:
        progress(f'Downloading {EMAIL_BASE_MODEL}…')
        with _ollama_json(base, '/api/pull', {'model': EMAIL_BASE_MODEL, 'stream': True},
                          timeout=600) as r:
            _stream(r, progress, f'Downloading {EMAIL_BASE_MODEL}…')
    progress(f'Creating {EMAIL_MODEL}…')
    try:
        with _ollama_json(base, '/api/create', {'model': EMAIL_MODEL, 'from': EMAIL_BASE_MODEL,
                                                'system': EMAIL_SYSTEM, 'stream': True},
                          timeout=300) as r:
            _stream(r)
    except Exception:
        # Older Ollama servers only understand the Modelfile form.
        modelfile = f'FROM {EMAIL_BASE_MODEL}\nSYSTEM "{EMAIL_SYSTEM}"'
        with _ollama_json(base, '/api/create', {'name': EMAIL_MODEL, 'modelfile': modelfile,
                                                'stream': True}, timeout=300) as r:
            _stream(r)
    if not had_base:
        try:
            _ollama_json(base, '/api/delete', {'model': EMAIL_BASE_MODEL}, method='DELETE').close()
        except Exception:
            pass
    if not email_model_installed(host):
        raise RuntimeError(f'{EMAIL_MODEL} not found after setup')
    progress(f'✓ {EMAIL_MODEL} ready')


def remove_email_model(host):
    _ollama_json(ollama_url(host), '/api/delete', {'model': EMAIL_MODEL},
                 method='DELETE', timeout=10).close()
