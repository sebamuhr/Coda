import subprocess
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

def create_icon():
    from PIL import ImageFont
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # White circle with thin black border
    draw.ellipse([2, 2, 62, 62], fill='white', outline='black', width=2)
    # Try to load a bold system font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except:
        font = ImageFont.load_default()
    # Center the C
    bbox = draw.textbbox((0, 0), "C", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[0]
    x = (64 - w) / 2 - 2
    y = (64 - h) / 2 - 4
    draw.text((x, y), "C", fill='black', font=font)
    return img


def launch_coda(icon, query):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Choose your project folder")
    if folder:
        cmd = f"cd '{folder}' && source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://192.168.2.200:11434 aider --model ollama/coda:2.0 ; exec bash"
        subprocess.Popen([
            'gnome-terminal', '--title=Coda 🤖', '--', 'bash', '-c', cmd
        ])

def quit_app(icon, query):
    icon.stop()

icon = pystray.Icon(
    "Coda",
    create_icon(),
    "Coda AI",
    menu=pystray.Menu(
        item('Launch Coda', launch_coda),
        item('Quit', quit_app)
    )
)

icon.run()
