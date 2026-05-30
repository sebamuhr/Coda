# Coda 🤖

> **Right-click any folder. Your local AI coding assistant appears. No subscription. No cloud. No limits.**

I was fed up with Cursor's $60/month subscription and hitting limits constantly. So I built my own offline coding assistant that lives on my machine, knows my files, and costs nothing to run.

This is Coda — a local AI coding assistant integrated directly into your Linux file manager.

---

## What It Does

- **System tray icon** — lives in your taskbar, click to launch Coda in any folder
- **Right-click any folder → Call Coda** — launches your AI coding assistant in that folder
- **Full file editing** — reads, creates, and modifies your project files
- **Git history on every change** — every edit is automatically committed with a description
- **Undo anytime** — `/undo` rolls back the last change instantly
- **100% offline** — your code never leaves your machine
- **No subscription** — runs on your own hardware with your own model

---

## How It Looks

Right click inside any project folder:
📁 My Project
└── [right click on empty space]
├── Open Terminal
├── Call Coda        ← your AI assistant
└── ...

A terminal opens with Coda ready to work:

create a weather app with vanilla HTML CSS and JS
fix the temperature conversion bug in app.js
add a dark mode toggle to index.html


---

## Requirements

- Linux (Debian/Ubuntu based — tested on Zorin OS and Ubuntu)
- [Ollama](https://ollama.ai) running locally or on a server on your network
- Any Ollama model (recommended: `qwen2.5-coder:32b` or similar)
- Python 3
- Nautilus file manager (GNOME)

---

## Installation

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/install.sh | bash
```

That's it! The installer will ask you a couple of questions and set everything up automatically — Aider, the terminal command, the right-click menu, and the system tray icon.

### Manual install

<details>
<summary>Click to expand manual installation steps</summary>

### 1. Install Aider

```bash
python3 -m venv ~/aider-env
source ~/aider-env/bin/activate
pip install aider-chat
```

### 2. Set up your launch alias

Add this to your `~/.bashrc`:

```bash
alias coda='source ~/aider-env/bin/activate && OLLAMA_API_BASE=http://YOUR_OLLAMA_IP:11434 aider --model ollama/YOUR_MODEL_NAME'
```

Then reload:
```bash
source ~/.bashrc
```

### 3. Install the right-click menu extension

```bash
sudo apt install python3-nautilus gir1.2-ayatanaappindicator3-0.1
sudo mkdir -p /usr/share/nautilus-python/extensions/
sudo cp coda_extension.py /usr/share/nautilus-python/extensions/
nautilus -q
```

### 4. Install the system tray icon (optional)

```bash
/usr/bin/pip3 install pystray pillow --break-system-packages
sudo apt install python3-tk
cp coda-tray.py ~/
/usr/bin/python3 ~/coda-tray.py &
```

</details>

---

## Usage

### From the system tray
1. Click the **C** icon in your taskbar
2. Click **Launch Coda**
3. Choose your project folder
4. Done!

### From the file manager
1. Open your project folder in Nautilus
2. Right-click on empty space inside the folder
3. Click **Call Coda**
4. Start giving instructions!

### From the terminal
```bash
cd ~/my-project
coda
```

### Inside Coda
/add .              # add all project files
/add index.html     # add a specific file
/undo               # undo last change
/diff               # see what changed
/ask                # ask a question without editing files
/exit               # quit

---

## Tips

- Launch Coda from your project folder — right click → Call Coda
- Use `/add .` to let Coda see all your files
- Keep instructions focused — one task at a time works best
- Every change is a git commit — you always have a full history

---

## Contributing

Pull requests welcome! Ideas for improvement:

- Support for other file managers (Dolphin, Thunar)
- Windows/Mac support
- Auto-start on login setup

---

## License

MIT — do whatever you want with it.

---
