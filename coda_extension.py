import subprocess
import urllib.parse
import gi
gi.require_version('Nautilus', '4.0')
from gi.repository import Nautilus, GObject

class CodaExtension(GObject.GObject, Nautilus.MenuProvider):
    def get_background_items(self, current_folder):
        return []

    def get_file_items(self, files):
        if len(files) != 1:
            return []
        file = files[0]
        if file.get_uri_scheme() != 'file':
            return []
        if not file.is_directory():
            return []
        folder = urllib.parse.unquote(file.get_uri().replace("file://", ""))
        item = Nautilus.MenuItem(
            name="CodaExtension::call_coda",
            label="Call Coda",
            tip="Launch Coda AI in this folder"
        )
        item.connect("activate", self.launch_coda, folder)
        return [item]

    def launch_coda(self, menu, folder):
        cmd = f"cd '{folder}' && source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://192.168.2.200:11434 aider --model ollama/coda:2.0 ; exec bash"
        subprocess.Popen([
            'gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd
        ])
