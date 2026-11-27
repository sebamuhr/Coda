---
name: coda
description: Installs and manages Coda (Linux, Windows, macOS), which adds "Call Coda" to the right-click menu of every folder so the user's coding agent (Claude Code, Codex, Cursor Agent, Gemini CLI or Aider) opens there in one click, plus a tray icon and a `coda` terminal command. Use when the user wants to open their coding agent from the file manager or a folder, set up or fix the right-click menu, switch which agent opens, or update or uninstall Coda.
---

# Coda

Coda lets the user right-click a folder in Files and choose **Call Coda**. A terminal opens there running their coding agent. This replaces typing `cd /long/path && claude` every time. Coda also has a tray icon (C) and a `coda` command that does the same from a terminal.

Everything runs on the user's own computer. Coda doesn't collect data and doesn't touch the agent's login: it only opens the agent in a folder.

The app's files are in `app/`, next to this file.

## Is Coda installed?

Run `coda doctor`.

- **Command not found:** Coda is not installed. Follow "Install" below.
- **It lists problems** (duplicates, leftovers): run `coda integrate`.
- **`agent … NOT FOUND`:** the chosen coding agent isn't installed. Tell the user, or switch agents (see "Switching the agent").

## Install

Ask the user which coding agent Call Coda should open. Suggest the one you're running in: `claude`, `codex`, `cursor-agent` or `gemini`. Then run:

```bash
bash "<this skill's folder>/app/install.sh" --yes --engine claude
```

On **Windows** (PowerShell; no administrator rights needed):

```powershell
powershell -ExecutionPolicy Bypass -File "<this skill's folder>\app\install.ps1" -Yes -Engine claude
```

- `--yes` asks nothing.
- The installer needs `sudo apt-get` for a few system packages on Ubuntu/Debian. If you can't enter a password, add `--skip-system` and tell the user to run `sudo apt install python3-venv python3-tk python3-nautilus gir1.2-ayatanaappindicator3-0.1`.
- Running it again is safe: it updates in place, keeps settings and removes old duplicate copies.
- Supports Linux (GNOME Files for the right-click menu), Windows 10/11 (Explorer right-click; on Windows 11 under "Show more options") and macOS (menu bar icon plus the `coda` command; Finder has no right-click entry).
- On Windows the `coda` command works in terminals opened after the install.

After installing, tell the user:
- Right-click any folder in Files → **Call Coda**. The menu item only appears while the C icon is in the tray.
- `coda` in any terminal starts a session in that folder.
- C icon → **Coding Agent** switches which agent opens.

## Switching the agent

The user can switch in the tray (C icon → *Coding Agent*) or in Preferences (`coda prefs`, *Call Coda* tab). For one session only:

```bash
coda code --engine codex /path/to/folder
```

## Commands

| Command | What it does |
|---|---|
| `coda` / `coda code [folder]` | start a session with the agent in this terminal |
| `coda open <folder>` | open a new terminal window with the agent in that folder |
| `coda tray` / `coda prefs` | start the tray icon / Preferences |
| `coda doctor` | show what is installed where and find problems |
| `coda integrate` | recreate the right-click menu, launcher and autostart |
| `coda update` | update Coda |
| `coda uninstall` | remove Coda completely (asks first; add `--yes` to skip the questions, `--keep-config` to keep settings) |

## Troubleshooting

- **No "Call Coda" in the right-click menu:**
  - Is the C icon in the tray? If not, run `coda tray`.
  - Run `coda integrate`, which reinstalls the menu entry and restarts Files.
  - On Ubuntu the `python3-nautilus` package must be installed.
  - On Windows 11 it is under right-click → **Show more options**. On Windows, Call Coda works even when the tray icon isn't running.
- **A terminal opens and says the agent isn't installed:** install that agent, or pick another one in Preferences.
- **Aider says an API key is missing:** the user adds it in Preferences → Call Coda. Never ask for keys in chat.

## Terms

Coda's [Terms of Use](app/TERMS.md) and [Privacy Policy](app/PRIVACY.md) are in `app/`. If the user asks about them, point them there. In short: Coda collects no data, and the user is responsible for how they use their agents.
