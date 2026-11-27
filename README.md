# Coda 🤖

> **Right-click any folder → your AI coding agent opens right there.**

No more `cd ~/some/long/path && claude` every time. Coda adds **Call Coda** to the right-click menu of every folder, and a small **C** icon to your system tray (Linux, Windows) or menu bar (macOS). One click, and Claude Code, Codex, Cursor Agent, Gemini CLI or Aider is working in that folder.

---

## Features at a Glance

| Feature | Description |
|---|---|
| **Right-click → Call Coda** | Opens your coding agent in any folder from the file manager (Linux with GNOME Files, and Windows) |
| **Launch Coda** | Folder picker from the tray icon to start a session anywhere |
| **`coda` command** | Type `coda` in any terminal to start a session in that folder |
| **Your agent, your login** | Claude Code, Codex, Cursor Agent, Gemini CLI or Aider: switch from the tray in one click |
| **Session fill level** | The C icon fills green → yellow → red as coding sessions open (up to 10) |
| **Fully offline option** | Aider with a local Ollama model: nothing leaves your machine |
| **Clean install & uninstall** | One command installs, `coda update` updates, `coda uninstall` removes every trace |
| **Privacy** | Coda collects nothing: no accounts, no analytics, no servers |

---

## Screenshots

![Right-click Call Coda in file manager](Call%20Coda.png)
![System tray icon](System%20tray.png)
![Coda coding terminal](Launch%20Coda.png)

---

## Coding agents

**Call Coda opens the coding agent you already use.** Pick one in Preferences or from the tray (*Coding Agent*):

| Agent | Notes |
|---|---|
| [Claude Code](https://claude.com/claude-code) | uses its own login |
| [Codex CLI](https://github.com/openai/codex) | uses its own login |
| [Cursor Agent](https://cursor.com/cli) | uses its own login |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | uses its own login |
| [Aider](https://aider.chat) | works with local Ollama models or a Gemini / Claude / OpenAI key: the 100 % offline option |

Coda never touches your agent's login: it just opens the agent, as published by its maker, in the folder you chose.

Start a session in three ways:

- **Right-click any folder → Call Coda** in your file manager *(Linux and Windows; see the notes below)*
- **C → Launch Coda** in the tray → pick a folder
- From the terminal:

```bash
cd ~/my-project
coda
```

> **Windows 11 note:** Call Coda is in the classic right-click menu: right-click a folder → **Show more options** → **Call Coda** (or Shift + right-click). The short Windows 11 menu only shows apps with a signed app package.
>
> **macOS note:** Finder doesn't let apps add right-click actions without a signed App Extension, so on macOS use **C → Launch Coda** from the menu bar or the `coda` command.

### With Aider

When Aider is your agent, pick its AI under **C → Aider Model**:

| Provider | Free tier | Notes |
|---|---|---|
| Ollama (local) | ✓ free forever | Private: runs on your machine or your own server |
| Gemini | ✓ free tier | Key at [aistudio.google.com](https://aistudio.google.com/apikey) |
| Claude | paid | Key at [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| OpenAI | paid | Key at [platform.openai.com](https://platform.openai.com/api-keys) |

Every change Aider makes is committed to git; `/undo` rolls back the last one. Other useful commands: `/add .`, `/diff`, `/ask`, `/exit`.

---

## Requirements

- **Linux:** Debian/Ubuntu based (tested on Zorin OS and Ubuntu); the right-click menu needs GNOME Files (Nautilus)
- **macOS:** Ventura or later, with [Homebrew](https://brew.sh)
- **Windows:** 10 or 11 (the installer sets up Python with winget if it is missing)
- Python 3.10+
- A coding agent (Claude Code, Codex, Cursor Agent, Gemini CLI), or Aider, which the installer can set up for you

---

## Install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/install.sh)
```

**Windows** (in PowerShell; no administrator rights needed):

```powershell
irm https://raw.githubusercontent.com/sebamuhr/Coda/main/install.ps1 | iex
```

The installer asks which coding agent to open. It is **safe to run again**: it updates in place, keeps your settings, and removes any old duplicate copies of Coda it finds.

Useful options: `--yes` (no questions), `--engine claude`, `--reconfigure`, `--no-autostart`. Run with `--help` for the full list. On Windows: `-Yes`, `-Engine claude`, `-NoAutostart`, passed like this:

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/sebamuhr/Coda/main/install.ps1))) -Engine claude
```

**From source (developers):**

```bash
git clone https://github.com/sebamuhr/Coda.git
cd Coda && ./install.sh
```

Coda then runs straight from your checkout, so your edits take effect on the next restart.

### Where Coda keeps things

| Path | What |
|---|---|
| `~/.local/share/coda/` | the app, its Python environment and (if used) Aider |
| `~/.config/coda/` | your settings (only readable by you) |
| `~/.local/bin/coda` | the `coda` command |
| `~/.config/autostart/coda.desktop`, `~/.local/share/applications/coda.desktop` | start on login, app menu entry (Linux) |
| `~/Library/LaunchAgents/com.coda.plist`, `~/Applications/Coda.app` | the same on macOS |
| `%LOCALAPPDATA%\Coda` (app, Python environment, `coda.cmd`), `%APPDATA%\Coda` (settings) | Windows; plus the right-click entry, start on login and the `coda` PATH entry in your user registry, and a Start menu shortcut |

Nothing is written to your shell config, and API keys are never placed on a command line.

### Commands

```bash
coda                 # coding session in the current folder
coda open ~/project  # coding session in a new terminal window
coda doctor          # check the install, find leftovers or duplicate copies
coda update          # update to the latest version
coda uninstall       # remove Coda completely
```

### Update

**C → Preferences → General → Update Coda**, or `coda update`.

### Uninstall

**C → Preferences → General → Uninstall Coda**, or `coda uninstall`. This removes the app, settings, launchers and the `coda` command. A git checkout of the source is never deleted.

If Coda is broken or half-removed:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/uninstall.sh)
```

On Windows: `irm https://raw.githubusercontent.com/sebamuhr/Coda/main/uninstall.ps1 | iex`

---

## Use Coda from your AI agent (skill)

Coda also ships as an agent skill (`skill/SKILL.md`; build the zip with `./make-skill.sh`). Ask Claude Code, Codex or Cursor to "set up Call Coda" and it installs Coda, sets the right agent and fixes the right-click menu if it ever goes missing.

---

## How it all fits together

```
Your desktop
│
├── System tray  (C icon)
│   ├── Launch Coda  ──────────────► folder picker → your coding agent
│   ├── Coding Agent  ─────────────► Claude Code, Codex, Cursor, Gemini or Aider
│   ├── Preferences  ──────────────► configure everything
│   └── Quit  ─────────────────────► closes everything cleanly
│
├── File manager right-click  (Linux, Windows)
│   └── Call Coda  ────────────────► coding terminal in that folder
│
└── Terminal
    └── coda  ─────────────────────► coding session in current folder
```

---

## Tips

- **Call Coda** only appears in the right-click menu while Coda is running; quit from the tray and it disappears
- The **fill level** on the C icon shows how many coding sessions are open
- Something odd? Run `coda doctor`: it shows what is installed where and how to fix leftovers

---

## The Story

I'm a no-code developer. I started with Cursor AI and loved it, but I got tired of opening a terminal, typing the long path to a project and starting the agent, every single time. So I made the folder itself the button: right-click, Call Coda, and the agent is there.

Nothing fancy. Just works.

---

## Contributing

Pull requests welcome! Ideas:

- Support for other file managers (Dolphin, Thunar)
- A signed package so Call Coda shows in the short Windows 11 menu
- A Finder extension for macOS

---

## License, terms and privacy

The code is MIT-licensed (see [LICENSE](LICENSE)).

Using Coda means you accept the [Terms of Use](TERMS.md). In short: Coda is a tool, you are responsible for how you use it and for what your AI agents do, and it comes with no warranty. Coda collects no data at all; see the [Privacy Policy](PRIVACY.md).

---

*Built with frustration, coffee, and a lot of help from Claude* ☕
