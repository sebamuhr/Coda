# Coda — Privacy Policy

*Last updated: 27 November 2026*

**Short version: Coda's author collects nothing. There are no accounts, no analytics, no telemetry and no Coda servers.**

## What stays on your computer

Coda stores its settings only on your own computer:

| What | Where |
|---|---|
| Settings: which coding agent to open and, if you use Aider, its AI provider, model and API key | `~/.config/coda/config.json`, readable only by your user account |
| The app itself | `~/.local/share/coda` (or the folder you installed it from) |

Running `coda uninstall` removes all of it.

## Where your data goes

Coda itself sends nothing anywhere. It only opens your coding agent in a folder:

- **Your coding agent** (Claude Code, Codex, Cursor Agent, Gemini CLI or Aider) sends whatever you work on to its provider, under that provider's own terms and privacy policy. Coda only starts it.
- **With Aider**, your code goes to the AI you picked: your own Ollama server (nothing leaves your machines) or Google, Anthropic or OpenAI with your API key.
- **GitHub**, only when you install or update Coda, to download the code.

What these services do with your data is governed by their own privacy policies, not this one.

## Children

Coda is not directed at children under 16.

## Changes and contact

This policy may be updated with new versions of Coda. Questions: https://github.com/sebamuhr/Coda/issues.
