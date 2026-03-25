#!/usr/bin/env bash
# PreToolUse hook: reminds agents to use indexer commands instead of Grep/Glob
# for symbol-level code navigation. Never blocks — only adds context.

set -euo pipefail

# Require jq for JSON parsing
command -v jq >/dev/null 2>&1 || { echo '{}'; exit 0; }

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')

# --- GREP HANDLING ---
if [ "$TOOL_NAME" = "Grep" ]; then
  PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern')

  # If pattern contains spaces or regex metacharacters, it's likely a real text search
  if echo "$PATTERN" | grep -qE '[ .*+?\[\](){}|^$\\]'; then
    echo '{}'
    exit 0
  fi

  IS_SYMBOL=false

  # CamelCase: e.g., ExecuteGenerateFlow, MyClass
  if echo "$PATTERN" | grep -qE '^[A-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*$'; then
    IS_SYMBOL=true
  fi

  # snake_case with underscores: e.g., execute_flow, my_func
  if echo "$PATTERN" | grep -qE '^[a-z][a-z0-9]*(_[a-z0-9]+)+$'; then
    IS_SYMBOL=true
  fi

  # PascalCase single word: e.g., Database, Config (3+ chars starting uppercase)
  if echo "$PATTERN" | grep -qE '^[A-Z][a-z][a-zA-Z0-9]{1,}$'; then
    IS_SYMBOL=true
  fi

  # ALL_CAPS constant: e.g., DEFAULT_IGNORE, MAX_RESULTS
  if echo "$PATTERN" | grep -qE '^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$'; then
    IS_SYMBOL=true
  fi

  if [ "$IS_SYMBOL" = true ]; then
    jq -n --arg pat "$PATTERN" '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": ("REMINDER: The pattern \u0027" + $pat + "\u0027 looks like a code symbol. Use `indexer search " + $pat + "` to find its definition, `indexer refs " + $pat + "` for references, or `indexer callers " + $pat + "` for callers. Use `indexer grep " + $pat + "` for full-text search. Only use Grep as a last resort. See CLAUDE.md.")
      }
    }'
    exit 0
  fi
fi

# --- GLOB HANDLING ---
if [ "$TOOL_NAME" = "Glob" ]; then
  GLOB_PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern')

  IS_EXPLORATION=false

  # Broad recursive code file search: **/*.py, **/*.go, etc.
  if echo "$GLOB_PATTERN" | grep -qE '^\*\*/\*\.(py|go|ts|tsx|js|jsx|rs|java|rb|c|cpp|h|hpp|cs)$'; then
    IS_EXPLORATION=true
  fi

  # Catch-all glob: **/*
  if echo "$GLOB_PATTERN" | grep -qE '^\*\*/\*$'; then
    IS_EXPLORATION=true
  fi

  # Brace expansion: **/*.{ts,tsx}
  if echo "$GLOB_PATTERN" | grep -qE '^\*\*/\*\.\{[a-z,]+\}$'; then
    IS_EXPLORATION=true
  fi

  if [ "$IS_EXPLORATION" = true ]; then
    jq -n '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": "REMINDER: This looks like broad code exploration. Use `indexer map --tokens 2048` for a ranked repo overview, `indexer find \"*.py\"` to find files by pattern, or `indexer tree` for directory structure. See CLAUDE.md."
      }
    }'
    exit 0
  fi
fi

# Default: no intervention
echo '{}'
exit 0
