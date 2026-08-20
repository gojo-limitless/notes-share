#!/usr/bin/env bash
# deploy.sh — render note(s) into site/ and push to GitHub Pages.
#
# Usage:
#   ./deploy.sh "<note title or ID>"     # render one note, then push everything
#   ./deploy.sh --all                    # re-render every note in notes.json, then push
#
# Requires GITHUB_TOKEN in ~/.hermes/.env (or exported) and the notes-share
# repo already created + Pages enabled (one-time setup; see README).
set -euo pipefail

cd "$(dirname "$0")"

# Load GITHUB_TOKEN from ~/.hermes/.env if not already set
if [ -z "${GITHUB_TOKEN:-}" ] && [ -f "$HOME/.hermes/.env" ]; then
  GITHUB_TOKEN="$(grep '^GITHUB_TOKEN=' "$HOME/.hermes/.env" | head -1 | cut -d= -f2- | tr -d '\n\r')"
fi
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN not set (expected in ~/.hermes/.env or environment)" >&2
  exit 1
fi

GH_USER="$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | python3 -c 'import sys,json; print(json.load(sys.stdin)["login"])')"
REPO="$GH_USER/notes-share"

if [ "${1:-}" = "--all" ]; then
  if [ ! -f site/notes.json ]; then
    echo "site/notes.json missing — nothing to re-render" >&2; exit 1
  fi
  python3 -c "
import json
for e in json.load(open('site/notes.json')):
    print(e['id'])" | while read -r id; do
    echo "→ re-rendering $id"
    python3 render_note.py "$id" >/dev/null
  done
else
  [ $# -ge 1 ] || { echo "Usage: $0 \"<note title or ID>\" | --all"; exit 1; }
  echo "→ rendering: $1"
  python3 render_note.py "$1"
fi

cd site
git add -A
if git diff --cached --quiet; then
  echo "No changes to push."
else
  git commit -m "Update shared notes" >/dev/null
  git push -u origin main
fi

echo
echo "URLs:"
echo "  hub:  https://$GH_USER.github.io/notes-share/"
GH_USER="$GH_USER" python3 - <<'EOF'
import json, os
user = os.environ["GH_USER"]
for e in json.load(open("notes.json")):
    print(f"  {e['title'][:50]!r}: https://{user}.github.io/notes-share/notes/{e['slug']}.html")
EOF
