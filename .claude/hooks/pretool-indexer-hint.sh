#!/usr/bin/env bash
# PreToolUse hook: remind Claude to use indexer commands instead of Grep/Glob
# This hook never blocks — it only adds helpful reminders via additionalContext.

set -euo pipefail

# Read the tool use JSON from stdin
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input // empty')

# Check if Grep is being used with symbol-like patterns
if [[ "$TOOL_NAME" == "Grep" ]]; then
  PATTERN=$(echo "$TOOL_INPUT" | jq -r '.pattern // empty')

  # Detect symbol-like patterns: CamelCase, PascalCase, snake_case, ALL_CAPS, or function-like
  if echo "$PATTERN" | grep -qE '(^[A-Z][a-z]+[A-Z]|^[a-z]+_[a-z]+|^[A-Z]{2,}_[A-Z]|^(def|class|function|func|fn) |^\w+\()'; then
    echo '{"additionalContext": "REMINDER: Use `indexer search <name>` to find symbol definitions, `indexer refs <symbol>` for references, or `indexer callers <symbol>` for callers. Use `indexer grep` for full-text search. See CLAUDE.md for details."}'
    exit 0
  fi

  # For any other Grep usage, suggest indexer grep
  echo '{"additionalContext": "REMINDER: Consider using `indexer grep <pattern>` for full-text search across indexed files. See CLAUDE.md for details."}'
  exit 0
fi

# Check if Glob is being used for broad code exploration
if [[ "$TOOL_NAME" == "Glob" ]]; then
  PATTERN=$(echo "$TOOL_INPUT" | jq -r '.pattern // empty')

  # Detect broad exploration patterns: **/*.ext, **/*, src/**/*.ext, etc.
  if echo "$PATTERN" | grep -qE '(\*\*/\*|\*\*/.+\.\w+$)'; then
    echo '{"additionalContext": "REMINDER: Use `indexer find <pattern>` to find files, `indexer tree [path]` for directory listing, or `indexer map --tokens 2048` for a ranked repo overview. See CLAUDE.md for details."}'
    exit 0
  fi
fi

# No reminder needed
echo '{}'
