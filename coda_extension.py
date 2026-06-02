import subprocess
import urllib.parse
import os
import json
import time as _time
import gi
gi.require_version('Nautilus', '4.0')
from gi.repository import Nautilus, GObject

MARKER_DIR = '/tmp/coda_terminals'

class CodaExtension(GObject.GObject, Nautilus.MenuProvider):

    def get_background_items(self, current_folder):
        return []

    def get_file_items(self, files):
        if not os.path.exists('/tmp/coda-running'):
            return []
        if len(files) != 1:
            return []
        f = files[0]
        if f.get_uri_scheme() != 'file' or not f.is_directory():
            return []
        folder = urllib.parse.unquote(f.get_uri().replace("file://", ""))
        menu_item = Nautilus.MenuItem(
            name="CodaExtension::call_coda",
            label="Call Coda",
            tip="Launch Coda AI in this folder"
        )
        menu_item.connect("activate", self.launch_coda, folder)
        return [menu_item]

    def _load_config(self):
        try:
            with open(os.path.expanduser('~/.config/coda/config.json')) as f:
                return json.load(f)
        except Exception:
            return {}

    def _build_cmd(self, folder, cfg, marker):
        provider  = cfg.get('provider', 'Ollama (local)')
        model     = cfg.get('model', 'coda:2.0')
        api_key   = cfg.get('api_key', '')
        ollama_ip = cfg.get('ollama_ip', 'localhost')
        activate  = "source ~/aider-env/bin/activate"

        if provider == "Ollama (local)":
            base_url = f"http://{ollama_ip}:11434" if ollama_ip else "http://localhost:11434"
            run = f"OLLAMA_API_BASE={base_url} aider --model ollama/{model}"
        elif provider == "Gemini":
            run = f"GEMINI_API_KEY={api_key} aider --model gemini/{model or 'gemini-1.5-pro'}"
        elif provider == "OpenAI":
            run = f"OPENAI_API_KEY={api_key} aider --model {model or 'gpt-4o'}"
        elif provider == "Claude":
            run = f"ANTHROPIC_API_KEY={api_key} aider --model {model or 'claude-opus-4-5'}"
        else:
            base_url = f"http://{ollama_ip}:11434"
            run = f"OLLAMA_API_BASE={base_url} aider --model ollama/{model}"

        return (
            f"mkdir -p {MARKER_DIR} && "
            f"touch '{marker}' && "
            f"trap 'rm -f \"{marker}\"' EXIT HUP INT TERM && "
            f"cd '{folder}' && {activate} && {run} ; bash"
        )

    def launch_coda(self, menu, folder):
        cfg      = self._load_config()
        marker   = os.path.join(MARKER_DIR, f'term_ext_{int(_time.time())}')
        cmd      = self._build_cmd(folder, cfg, marker)
        provider = cfg.get('provider', 'Ollama (local)')
        subprocess.Popen([
            'gnome-terminal',
            f'--title=Coda · {provider}',
            '--', 'bash', '-c', cmd
        ])
