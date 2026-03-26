#!/usr/bin/env bash
# Install/upgrade the indexer CLI tool and Claude skills globally.
# Usage: bash install.sh  (or: ./install.sh)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_SRC="$REPO_DIR/.claude/skills"
SKILLS_DST="$HOME/.claude/skills"

# 1. Install/upgrade the CLI tool
echo "Installing indexer CLI tool..."
uv tool install --force --editable "$REPO_DIR"
echo "  Done: $(which indexer)"

# 2. Sync skills
echo "Installing Claude skills..."
mkdir -p "$SKILLS_DST"
for skill_dir in "$SKILLS_SRC"/*/; do
  skill_name="$(basename "$skill_dir")"
  mkdir -p "$SKILLS_DST/$skill_name"
  cp "$skill_dir"SKILL.md "$SKILLS_DST/$skill_name/SKILL.md"
  echo "  $skill_name"
done

# 3. Allow-list indexer commands globally (read-only, non-destructive)
GLOBAL_SETTINGS="$HOME/.claude/settings.json"
INDEXER_PERMISSIONS=(
  "Bash(indexer map:*)"
  "Bash(indexer search:*)"
  "Bash(indexer refs:*)"
  "Bash(indexer callers:*)"
  "Bash(indexer impl:*)"
  "Bash(indexer skeleton:*)"
  "Bash(indexer grep:*)"
  "Bash(indexer find:*)"
  "Bash(indexer tree:*)"
  "Bash(indexer stats:*)"
  "Bash(indexer init:*)"
  "Bash(indexer update:*)"
  "Bash(indexer config:*)"
  "Bash(indexer --help:*)"
)

if command -v jq >/dev/null 2>&1; then
  echo "Adding indexer permissions to global Claude settings..."
  if [ -f "$GLOBAL_SETTINGS" ]; then
    existing="$(<"$GLOBAL_SETTINGS")"
  else
    mkdir -p "$(dirname "$GLOBAL_SETTINGS")"
    existing='{}'
  fi

  # Build JSON array of permissions to add
  perms_json='[]'
  for perm in "${INDEXER_PERMISSIONS[@]}"; do
    perms_json=$(echo "$perms_json" | jq --arg p "$perm" '. + [$p]')
  done

  # Merge: add any permissions not already present
  echo "$existing" | jq --argjson new "$perms_json" '
    .permissions.allow = ((.permissions.allow // []) + $new | unique)
  ' > "$GLOBAL_SETTINGS"
  echo "  Done: $GLOBAL_SETTINGS"
else
  echo "Warning: jq not found — skipping global permission setup."
  echo "  Manually add indexer permissions to $GLOBAL_SETTINGS or run /setup-indexer in each project."
fi

echo "Done."
