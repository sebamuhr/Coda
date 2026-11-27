# Coda — Privacy Policy

*Last updated: 27 November 2026*

**Short version: Coda's author collects nothing. There are no accounts, no analytics, no telemetry and no Coda servers.**

## What stays on your computer

Coda stores its settings and data only on your own computer:

| What | Where |
|---|---|
| Settings, including your email address, app password and any API keys | `~/.config/coda/config.json`, readable only by your user account |
| Your notes about contacts | `~/.config/coda/` |
| The app itself | `~/.local/share/coda` (or the folder you installed it from) |

Running `coda uninstall` removes all of it.

## Where your data goes, and only when you use that feature

Coda connects only to the services you set up yourself:

- **Your email provider** (for example Gmail) uses IMAP and SMTP to read your mail and to save or send messages.
- **Your local or home Ollama server.** This is the default email writer, so your emails don't leave your own machines.
- **A cloud AI provider (Anthropic, Google or OpenAI), only if you choose one** in Preferences → Email → *Writes with*. Coda warns you before switching. The writer then receives the email thread you are replying to, your instructions and your notes about that contact. It never receives your mail password.
- **Your coding agent** (Claude Code, Codex, etc.) sends whatever you work on to its provider under that provider's own privacy policy. Coda only opens it.
- **GitHub**, only when you install or update Coda, to download the code.

What these services do with your data is governed by their own privacy policies, not this one.

## Using Coda as an AI skill

If you use the Coda skill inside an AI agent, the agent reads the emails you ask it to work with. Those emails then go to that agent's provider under that provider's terms. The skill tells the agent never to ask for, read or print your mail password.

## Children

Coda is not directed at children under 16.

## Changes and contact

This policy may be updated with new versions of Coda. Questions: https://github.com/sebamuhr/Coda/issues.
