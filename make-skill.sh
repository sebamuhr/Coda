#!/usr/bin/env bash
# Build dist/coda-skill.zip for agent-skill marketplaces (e.g. agensi.io):
#   SKILL.md at the root, the app in app/.
set -euo pipefail
cd "$(dirname "$0")"
VERSION=$(python3 -c "import coda_common as C; print(C.VERSION)")
OUT="dist/coda-skill-$VERSION.zip"
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/app" dist
cp skill/SKILL.md "$STAGE/"
cp install.sh uninstall.sh coda.py coda_common.py coda_mail.py \
   coda-tray.py coda-email.py coda-preferences.py coda_extension.py \
   LICENSE README.md TERMS.md PRIVACY.md "$STAGE/app/"
chmod +x "$STAGE/app/install.sh" "$STAGE/app/uninstall.sh" "$STAGE/app/coda.py"

# Frontmatter sanity check: name + description are required.
python3 - "$STAGE/SKILL.md" <<'EOF'
import re, sys
text = open(sys.argv[1]).read()
m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
assert m, 'SKILL.md has no frontmatter'
fm = dict(l.split(':', 1) for l in m.group(1).splitlines() if ':' in l)
name, desc = fm.get('name', '').strip(), fm.get('description', '').strip()
assert re.fullmatch(r'[a-z0-9-]{1,64}', name), f'bad name: {name!r}'
assert 0 < len(desc) <= 1024, f'description must be 1–1024 chars (is {len(desc)})'
print(f'  SKILL.md ok — name={name}, description {len(desc)} chars')
EOF

rm -f "$OUT"
(cd "$STAGE" && zip -qr -X "$OLDPWD/$OUT" .)
echo "  built $OUT"
unzip -l "$OUT" | tail -n +4 | head -n -2
