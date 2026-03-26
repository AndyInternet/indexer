#!/usr/bin/env bash
# Install/upgrade the indexer CLI tool and Claude commands globally.
# Usage: bash install.sh  (or: ./install.sh)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
COMMANDS_SRC="$REPO_DIR/claude/commands"
HOOKS_SRC="$REPO_DIR/claude/hooks"
COMMANDS_DST="$HOME/.claude/commands"
HOOKS_DST="$HOME/.claude/hooks"

# 1. Install/upgrade the CLI tool
echo "Installing indexer CLI tool..."
uv tool install --force --editable "$REPO_DIR"
echo "  Done: $(which indexer)"

# 2. Sync commands
echo "Installing Claude commands..."
mkdir -p "$COMMANDS_DST"
for cmd_file in "$COMMANDS_SRC"/*.md; do
  cmd_name="$(basename "$cmd_file")"
  cp "$cmd_file" "$COMMANDS_DST/$cmd_name"
  echo "  ${cmd_name%.md}"
done

# 3. Install PreToolUse hook
echo "Installing PreToolUse hook..."
mkdir -p "$HOOKS_DST"
cp "$HOOKS_SRC/pretool-indexer-hint.sh" "$HOOKS_DST/pretool-indexer-hint.sh"
chmod +x "$HOOKS_DST/pretool-indexer-hint.sh"
echo "  Done: $HOOKS_DST/pretool-indexer-hint.sh"

# 4. Allow-list indexer commands and register hook globally
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
  echo "Adding indexer permissions and hook to global Claude settings..."
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

  # Merge: add permissions and PreToolUse hook
  echo "$existing" | jq --argjson new "$perms_json" --arg hook_cmd "bash $HOOKS_DST/pretool-indexer-hint.sh" '
    .permissions.allow = ((.permissions.allow // []) + $new | unique)
    | .hooks.PreToolUse = (
        [(.hooks.PreToolUse // [])[] | select(
          (.hooks // []) | any(.command | test("pretool-indexer-hint")) | not
        )]
        + [{
            "matcher": "Grep|Glob",
            "hooks": [{"type": "command", "command": $hook_cmd}]
          }]
      )
  ' > "$GLOBAL_SETTINGS"
  echo "  Done: $GLOBAL_SETTINGS"
else
  echo "Warning: jq not found — skipping global settings setup."
  echo "  Manually add indexer permissions and hook to $GLOBAL_SETTINGS or run /indexer-setup in each project."
fi

echo "Done."
