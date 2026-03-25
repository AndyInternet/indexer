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

echo "Done."
