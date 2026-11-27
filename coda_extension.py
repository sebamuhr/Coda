"""Files (Nautilus) right-click menu: "Call Coda" on a folder or in a folder's background.

Installed by `coda integrate` into ~/.local/share/nautilus-python/extensions/.
It holds no logic of its own — it hands the folder to the `coda` command, so it
always launches exactly the way the tray does.
"""
import os
import subprocess
import urllib.parse

import gi
gi.require_version('Nautilus', '4.0')
from gi.repository import GObject, Nautilus  # noqa: E402

CODA = os.path.expanduser('~/.local/bin/coda')


def _runtime_flag():
    rt = os.environ.get('XDG_RUNTIME_DIR')
    base = os.path.join(rt, 'coda') if rt and os.path.isdir(rt) else f'/tmp/coda-{os.getuid()}'
    return os.path.join(base, 'running')


def _path(f):
    if f.get_uri_scheme() != 'file':
        return None
    return urllib.parse.unquote(f.get_uri()[len('file://'):])


class CodaExtension(GObject.GObject, Nautilus.MenuProvider):

    def _item(self, name, folder):
        if not (os.access(CODA, os.X_OK) and os.path.exists(_runtime_flag())):
            return []   # only offered while the Coda tray is running
        item = Nautilus.MenuItem(name=f'CodaExtension::{name}', label='Call Coda',
                                 tip='Open a Coda coding session in this folder')
        item.connect('activate', lambda *_: subprocess.Popen([CODA, 'open', folder],
                                                              start_new_session=True))
        return [item]

    def get_file_items(self, *args):
        files = args[-1]
        if len(files) != 1 or not files[0].is_directory():
            return []
        folder = _path(files[0])
        return self._item('call_coda', folder) if folder else []

    def get_background_items(self, *args):
        folder = _path(args[-1])
        return self._item('call_coda_here', folder) if folder else []
