import subprocess
from tkinter import filedialog
import tkinter as tk

root = tk.Tk()
root.withdraw()

folder = filedialog.askdirectory(title="Choose your project folder")

if folder:
    cmd = f'cd "{folder}" && source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://192.168.2.200:11434 aider --model ollama/coda:2.0 ; exec bash'
    subprocess.Popen([
    'gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd
])
