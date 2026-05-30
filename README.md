# Coda 🤖

> **Right-click any folder. Your local AI coding assistant appears. No subscription. No cloud. No limits.**

I was fed up with Cursor's $20/month subscription and hitting limits constantly. So I built my own offline coding assistant that lives on my machine, knows my files, and costs nothing to run.

This is Coda — a local AI coding assistant integrated directly into your Linux file manager.

---

## What It Does

- **Right-click any folder → Call Coda** — launches your AI coding assistant in that folder
- **Full file editing** — reads, creates, and modifies your project files
- **Git history on every change** — every edit is automatically committed with a description
- **Undo anytime** — `/undo` rolls back the last change instantly
- **100% offline** — your code never leaves your machine
- **No subscription** — runs on your own hardware with your own model

---

## How It Looks

Right click inside any project folder:

```
📁 My Project
  └── [right click on empty space]
        ├── Open Terminal
        ├── Call Coda        ← your AI assistant
        └── ...
```

A terminal opens with Coda ready to work:

```
> create a weather app with vanilla HTML CSS and JS
> fix the temperature conversion bug in app.js
> add a dark mode toggle to index.html
```

---

## Requirements

- Linux (Debian/Ubuntu based — tested on Zorin OS and Ubuntu)
- [Ollama](https://ollama.ai) running locally or on a server on your network
- Any Ollama model (recommended: `qwen2.5-coder:32b` or similar)
- Python 3
- Nautilus file manager (GNOME)

---

## Installation

### 1. Install Aider

Aider is the engine that connects your model to your files.

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

Replace `YOUR_OLLAMA_IP` with your Ollama server IP (or `localhost` if running locally) and `YOUR_MODEL_NAME` with your model (e.g. `qwen2.5-coder:32b`).

Then reload:
```bash
source ~/.bashrc
```

### 3. Install the system tray icon (optional)

```bash
/usr/bin/pip3 install pystray pillow --break-system-packages
sudo apt install python3-tk
cp coda-tray.py ~/
/usr/bin/python3 ~/coda-tray.py &
```

### 4. Install the right-click menu extension

This is the magic — **Call Coda** appears directly when you right-click inside any folder.

```bash
sudo apt install python3-nautilus gir1.2-ayatanaappindicator3-0.1
mkdir -p /usr/share/nautilus-python/extensions/
sudo cp coda_extension.py /usr/share/nautilus-python/extensions/
nautilus -q
```

### 5. Install the desktop launcher (optional)

For a folder picker dialog you can launch from anywhere:

```bash
sudo apt install python3-tk
cp coda-launcher.py ~/
python3 ~/coda-launcher.py
```

---

## Usage

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
```
/add .              # add all project files
/add index.html     # add a specific file
/undo               # undo last change
/diff               # see what changed
/ask                # ask a question without editing files
/exit               # quit
```

---

## Tips

- Always launch Coda from inside your project folder
- Use `/add .` to let Coda see all your files
- Keep instructions focused — one task at a time works best
- Every change is a git commit — you always have a full history

---

## The Story

I'm a no-code developer. I started with Cursor AI and loved it — but $60/month adds up fast, especially when you hit the limits. I wanted something I owned, something offline, something that didn't send my code to servers I don't control.

Coda is what I built. It's Aider + Ollama + a bit of Python glue that integrates the whole thing into your desktop. Nothing fancy. Just works.

---

## Contributing

Pull requests welcome! Ideas for improvement:

- One-line installer script
- Support for other file managers (Dolphin, Thunar)
- Windows/Mac support
- Auto-start on login setup

---

## License

MIT — do whatever you want with it.

---

*Built with frustration, coffee, and a lot of help from Claude* ☕
