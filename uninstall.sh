#!/usr/bin/env bash
# Uninstall the indexer CLI tool and remove Claude commands/skills and permissions.
# Usage: bash uninstall.sh  (or: ./uninstall.sh)
set -euo pipefail

COMMANDS_DST="$HOME/.claude/commands"
SKILLS_DST="$HOME/.claude/skills"
GLOBAL_SETTINGS="$HOME/.claude/settings.json"

# 1. Uninstall the CLI tool
echo "Uninstalling indexer CLI tool..."
if uv tool uninstall indexer 2>/dev/null; then
  echo "  Done."
else
  echo "  Not installed (or not managed by uv)."
fi

# 2. Remove commands
echo "Removing Claude commands..."
for cmd in indexer-setup indexer-index indexer-explore; do
  if [ -f "$COMMANDS_DST/$cmd.md" ]; then
    rm "$COMMANDS_DST/$cmd.md"
    echo "  Removed $cmd"
  fi
done

# 3. Remove skills (legacy location)
echo "Removing Claude skills..."
for skill in indexer-setup indexer-index indexer-explore; do
  if [ -d "$SKILLS_DST/$skill" ]; then
    rm -r "$SKILLS_DST/$skill"
    echo "  Removed $skill"
  fi
done

# 4. Remove PreToolUse hook
HOOKS_DST="$HOME/.claude/hooks"
echo "Removing PreToolUse hook..."
if [ -f "$HOOKS_DST/pretool-indexer-hint.sh" ]; then
  rm "$HOOKS_DST/pretool-indexer-hint.sh"
  echo "  Removed $HOOKS_DST/pretool-indexer-hint.sh"
else
  echo "  Not found (already removed)."
fi

# 5. Remove indexer permissions and hook from global settings
if command -v jq >/dev/null 2>&1 && [ -f "$GLOBAL_SETTINGS" ]; then
  echo "Removing indexer permissions and hook from global Claude settings..."
  jq '
    if .permissions.allow then
      .permissions.allow = [.permissions.allow[] | select(startswith("Bash(indexer ") | not)]
    else . end
    | if .hooks.PreToolUse then
        .hooks.PreToolUse = [.hooks.PreToolUse[] | select(
          (.hooks // []) | any(.command | test("pretool-indexer-hint")) | not
        )]
        | if (.hooks.PreToolUse | length) == 0 then del(.hooks.PreToolUse) else . end
        | if (.hooks | length) == 0 then del(.hooks) else . end
      else . end
  ' "$GLOBAL_SETTINGS" > "$GLOBAL_SETTINGS.tmp" && mv "$GLOBAL_SETTINGS.tmp" "$GLOBAL_SETTINGS"
  echo "  Done: $GLOBAL_SETTINGS"
else
  if [ -f "$GLOBAL_SETTINGS" ]; then
    echo "Warning: jq not found — skipping settings cleanup."
    echo "  Manually remove indexer permissions and hook from $GLOBAL_SETTINGS"
  fi
fi

echo "Done."
