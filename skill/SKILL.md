---
name: coda
description: Installs and runs Coda, a private desktop companion for your coding agent. Adds "Call Coda" to the right-click menu of any folder so Claude Code, Codex, Cursor Agent, Gemini CLI or Aider opens there instantly, and lets you read your email and write replies in the user's own voice, saved as drafts, through the user's own mail account with no third-party servers. Use when the user wants to open their coding agent from the file manager, set up or fix the right-click menu, or read, answer or draft email.
---

# Coda

Coda has two parts. Both run on the user's own computer:

1. **Call Coda.** The user right-clicks a folder in Files and chooses **Call Coda**. A terminal opens there running their coding agent. This replaces typing `cd /long/path && claude` every time.
2. **Email.** You read the user's inbox and write replies in their voice. Replies are saved as **drafts** in the user's own mailbox, and the user sends them.

All commands go through the `coda` command. The app's files are in `app/`, next to this file.

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

- `--yes` asks nothing and never downloads the 2 GB email model.
- The installer needs `sudo apt-get` for a few system packages on Ubuntu/Debian. If you can't enter a password, add `--skip-system` and tell the user to run `sudo apt install python3-venv python3-tk python3-nautilus gir1.2-ayatanaappindicator3-0.1`.
- Running it again is safe: it updates in place, keeps settings and removes old duplicate copies.
- Supports Linux (GNOME Files for the right-click menu) and macOS (menu bar icon plus the `coda` command; Finder has no right-click entry).

After installing, tell the user:
- Right-click any folder in Files → **Call Coda**. The menu item only appears while the C icon is in the tray.
- `coda` in any terminal starts a session in that folder.
- **Email needs their address and an app password.** They type these into the C icon → **Preferences → Email** themselves (`coda prefs` opens it). Never ask for the password in chat and never put it on a command line.

## Switching the agent

The user can switch in the tray (C icon → *Coding Agent*) or in Preferences. You can also set it directly:

```bash
coda code --engine codex /path/to/folder        # one session only
```

To change the default, run `coda prefs` and pick the agent on the *Call Coda* tab.

## Email

First check that the account works:

```bash
coda mail check
```

If no account is set up, ask the user to fill in Preferences → Email (see above) and stop there.

### Reading

```bash
coda mail list                       # recent inbox; ● = unread
coda mail list --unread --json       # machine-readable
coda mail list --folder sent -n 5
coda mail read "<message-id>"        # the message plus its whole thread, and the user's notes on the sender
coda mail read "<message-id>" --json
```

Take message ids exactly as `list` prints them, angle brackets included, and quote them.

### Writing replies in the user's voice

1. Read the thread with `coda mail read`.
2. Read the **private notes** about the sender if there are any. They describe the relationship and the tone (e.g. "my sister: warm, informal").
   - Use them only to shape tone and word choice.
   - Never quote them, mention them or let them leak into the email.
3. Write as the user, in the first person. The `you.name` field in `--json` output is the user's name; sign with it. Match the language of the thread. Keep the length and formality the sender used.
4. Show the user the draft text and adjust it until they're happy with it.
5. Save it as a draft:

```bash
coda mail draft --reply-to "<message-id>" --body-file - <<'EOF'
Hi Ana,

Tuesday at 10 works for me. Could you bring last month's numbers?

Sam
EOF
```

`--reply-to` fills in the recipient and the `Re:` subject, and threads the draft correctly. For a new email, use `--to` and `--subject` instead.

### Sending

**Default to drafts.** Only send when the user explicitly asks you to send, and only after they've seen the final text:

```bash
coda mail send --reply-to "<message-id>" --body-file - --confirm <<'EOF'
...
EOF
```

`send` refuses to run without `--confirm`.

### Contact notes

`coda mail contacts` lists the user's notes per contact. `coda mail contacts someone@example.com` shows one person's notes. The user edits them in the Email Agent window, on the Contacts tab (`coda email`).

## Privacy rules

- Email content stays between this computer, the user's mail provider and you. Don't send it to any other tool, website or API, and don't save it to files outside the user's project.
- Never print, log or ask for the app password. It is stored in `~/.config/coda/config.json`, which only the user can read; don't open that file.
- Coda's own Email Agent window writes with a local model (`coda2.0:3b` via Ollama) by default. The user can switch it to Claude, Gemini or OpenAI in Preferences → Email; leave that choice to them. Run `coda email-model` only if the user asks for it: it downloads about 2 GB.

- Coda's [Terms of Use](app/TERMS.md) and [Privacy Policy](app/PRIVACY.md) are in `app/`. If the user asks about them, point them there. In short: Coda collects no data, and the user is responsible for what is sent in their name.

## Other commands

| Command | What it does |
|---|---|
| `coda open <folder>` | open a new terminal window with the agent in that folder |
| `coda tray` / `coda email` / `coda prefs` | start the tray icon / Email Agent window / Preferences |
| `coda doctor` | show what is installed where and find problems |
| `coda update` | update Coda |
| `coda uninstall` | remove Coda completely (asks first; add `--yes` to skip the questions, `--keep-config` to keep settings) |

## Troubleshooting

- **No "Call Coda" in the right-click menu:**
  - Is the C icon in the tray? If not, run `coda tray`.
  - Run `coda integrate`, which reinstalls the menu entry and restarts Files.
  - On Ubuntu the `python3-nautilus` package must be installed.
- **A terminal opens and says the agent isn't installed:** install that agent, or pick another one in Preferences.
- **Email login fails:** for Gmail, the user needs 2-Step Verification and an app password from myaccount.google.com/apppasswords, not their normal password. Outlook and Yahoo work the same way.
