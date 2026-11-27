#!/usr/bin/env bash
# Remove Coda completely — works even if the install is broken or half-removed.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/sebamuhr/Coda/main/uninstall.sh)
#
# Options are passed to `coda uninstall`: --yes, --keep-config, --keep-model
set -euo pipefail
DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/coda"

# Prefer the installed copy; fall back to one next to this script; else fetch.
for d in "$DATA_DIR/app" "$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)" "$HOME/Coda"; do
    if [ -f "$d/coda.py" ] && [ -f "$d/coda_common.py" ]; then
        # Run from a temp copy: the uninstaller deletes the directory it lives in.
        TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
        cp "$d/coda.py" "$d/coda_common.py" "$TMP/"
        python3 "$TMP/coda.py" uninstall "$@"; exit $?
    fi
done
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
for f in coda.py coda_common.py; do
    curl -fsSL "https://raw.githubusercontent.com/sebamuhr/Coda/main/$f" -o "$TMP/$f"
done
python3 "$TMP/coda.py" uninstall "$@"
