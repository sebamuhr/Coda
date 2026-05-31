# Coda 🤖

> **Your local AI assistant. Right-click any folder to code. Write emails in plain language. No subscription. No cloud. No limits.**

I was fed up with AI subscriptions and hitting limits constantly. So I built my own offline AI assistant that lives on my machine, knows my files, writes my emails, and costs nothing to run.

This is Coda — a local AI assistant integrated directly into your Linux desktop.

---

## What It Does

- **System tray icon** — lives in your taskbar, always one click away
- **Right-click any folder → Call Coda** — launches your AI coding assistant in that folder
- **Email Agent** — reads your inbox, writes replies in plain language, saves to Gmail Drafts or sends directly
- **Full file editing** — reads, creates, and modifies your project files
- **Git history on every change** — every edit is automatically committed with a description
- **Undo anytime** — `/undo` rolls back the last change instantly
- **Any AI provider** — Ollama (local), Claude API, OpenAI, Groq, or any custom endpoint
- **Preferences window** — configure everything from a clean UI, no config files to edit
- **100% private** — your code and emails never leave your machine when using local models
- **No subscription** — runs on your own hardware with your own model

---

## How It Looks

![Right-click menu](Call%20Coda.png)
![System tray icon](System%20tray.png)
![Coda terminal](Launch%20Coda.png)

---

## Coding Assistant

Right click any project folder → **Call Coda** — a terminal opens with your AI ready:

```
> create a weather app with vanilla HTML CSS and JS
> fix the temperature conversion bug in app.js  
> add a dark mode toggle to index.html
> explain what this function does
```

Every change is a git commit. Undo anything with `/undo`.

---

## Email Agent

Click **C → Email Agent** in your system tray:

- **Unread, Read, Drafts tabs** — browse your inbox
- **Select an email** — Coda reads the conversation for context
- **Describe your reply in plain language** — *"tell him Tuesday works but not Wednesday"*
- **Coda writes the full professional email**
- **Save to Drafts** — appears in Gmail ready to review and send
- **Send Now** — sends directly without leaving Coda
- **New Email tab** — write fresh emails from scratch the same way

Your emails stay on your machine. Coda connects directly to Gmail (or any IMAP provider) via App Password — no third party involved.

---

## Requirements

- Linux (Debian/Ubuntu based — tested on Zorin OS and Ubuntu)
- Python 3
- Nautilus file manager (GNOME)
- For coding: [Ollama](https://ollama.ai), Claude API, OpenAI, Groq, or any OpenAI-compatible endpoint
- For email: Gmail App Password (or any IMAP/SMTP provider)

---

## Installation

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/install.sh | bash
```

The installer asks a few questions and sets everything up automatically — Aider, the terminal command, the right-click menu, the system tray icon, and the email agent.

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

### 4. Install the system tray and email agent

```bash
/usr/bin/pip3 install pystray pillow requests --break-system-packages
sudo apt install python3-tk wmctrl libnotify-bin
mkdir -p ~/Coda
cp coda-tray.py coda-email.py coda-preferences.py ~/Coda/
/usr/bin/python3 ~/Coda/coda-tray.py &
```

### 5. Configure

Click **C → Preferences** in your system tray and fill in your AI provider and email settings.

</details>

---

## Usage

### Coding

```
Right-click any folder → Call Coda
```

Or from the tray: **C → Launch Coda** → choose folder

Or from terminal:
```bash
cd ~/my-project
coda
```

Inside Coda:
```
/add .              # add all project files
/add index.html     # add a specific file  
/undo               # undo last change
/diff               # see what changed
/ask                # ask without editing files
/exit               # quit
```

### Email

```
Click C in taskbar → Email Agent
```

1. Pick **Unread**, **Read**, or **Drafts** tab
2. Click an email
3. Type what you want to say in plain language
4. Click **Write Reply**
5. Review Coda's reply
6. **Save to Drafts** or **Send Now**

### Preferences

```
Click C in taskbar → Preferences
```

Configure your AI provider, model, API keys, email account, and general settings — all from one window. No config files to edit manually.

---

## Supported AI Providers

| Provider | Works for |
|----------|-----------|
| Ollama (local) | Coding + Email — fully offline |
| Claude API | Coding |
| OpenAI | Coding |
| Groq | Coding |
| Custom endpoint | Coding |

---

## Tips

- The **Call Coda** right-click menu only appears when Coda is running — quit from the tray and it disappears
- Use `/add .` to let Coda see all your project files
- Keep instructions focused — one task at a time works best
- Every change is a git commit — you always have a full history
- For email, **Save to Drafts** is safer — review in Gmail before sending

---

## The Story

I'm a no-code developer. I started with Cursor AI and loved it — but the monthly subscription adds up fast, especially when you hit the limits. I wanted something I owned, something offline, something that didn't send my code to servers I don't control.

Coda is what I built. It's Aider + Ollama + Python glue that integrates the whole thing into your Linux desktop. A coding assistant, an email agent, a preferences window — all in one system tray icon.

Nothing fancy. Just works.

---

## Contributing

Pull requests welcome! Ideas for improvement:

- Support for other file managers (Dolphin, Thunar)
- Windows/Mac support
- More email providers
- Calendar integration

---

## License

MIT — do whatever you want with it.

---

*Built with frustration, coffee, and a lot of help from Claude* ☕
