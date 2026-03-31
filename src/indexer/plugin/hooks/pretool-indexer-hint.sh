#!/usr/bin/env bash
# PreToolUse hook: redirects agents to use indexer commands instead of
# Grep/Glob/Bash for code navigation. Denies the tool call and provides
# the appropriate indexer alternative.

set -euo pipefail

# Require jq for JSON parsing
command -v jq >/dev/null 2>&1 || { echo '{}'; exit 0; }

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')

deny() {
  jq -n --arg reason "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
  exit 0
}

# --- LSP HANDLING ---
# The LSP tool (displays as "Search" in output) should use indexer instead.
if [ "$TOOL_NAME" = "LSP" ]; then
  PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern // .tool_input.query // ""')
  deny "Use \`indexer search $PATTERN\` to find definitions, \`indexer refs $PATTERN\` for references, or \`indexer callers $PATTERN\` for callers. Use \`indexer grep \"$PATTERN\"\` for full-text search."
fi

# --- GREP HANDLING ---
# All Grep calls should use indexer. Symbol-like patterns get specific
# suggestions (search/refs/callers); everything else gets indexer grep.
if [ "$TOOL_NAME" = "Grep" ]; then
  PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern')

  IS_SYMBOL=false

  # Only check for symbols if the pattern has no spaces or regex metacharacters
  if ! echo "$PATTERN" | grep -qE '[ .*+?\[\](){}|^$\\]'; then

    # camelCase: e.g., handleRequest, getElementById, useState, onClick
    if echo "$PATTERN" | grep -qE '^_{0,2}[a-z][a-z0-9]*([A-Z][a-zA-Z0-9]*)+$'; then
      IS_SYMBOL=true
    fi

    # PascalCase / CamelCase (uppercase start): e.g., MyClass, ExecuteFlow, HTTPServer
    if echo "$PATTERN" | grep -qE '^_{0,2}[A-Z][a-zA-Z0-9]{2,}$'; then
      IS_SYMBOL=true
    fi

    # snake_case: e.g., execute_flow, _private_func, __init__, __dunder__
    if echo "$PATTERN" | grep -qE '^_{0,2}[a-z][a-z0-9]*(_[a-z0-9]+)*_{0,2}$' && echo "$PATTERN" | grep -qE '_'; then
      IS_SYMBOL=true
    fi

    # SCREAMING_SNAKE_CASE: e.g., DEFAULT_IGNORE, _MAX_RESULTS, __ALL_CAPS
    if echo "$PATTERN" | grep -qE '^_{0,2}[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$'; then
      IS_SYMBOL=true
    fi

    # $-prefixed (JS/TS): e.g., $scope, $emit, $store, $onClick
    if echo "$PATTERN" | grep -qE '^\$[a-zA-Z][a-zA-Z0-9]*$'; then
      IS_SYMBOL=true
    fi
  fi

  if [ "$IS_SYMBOL" = true ]; then
    deny "The pattern '$PATTERN' looks like a code symbol. Use \`indexer search $PATTERN\` to find its definition, \`indexer refs $PATTERN\` for references, or \`indexer callers $PATTERN\` for callers. Use \`indexer grep $PATTERN\` for full-text search."
  fi

  # All other Grep patterns: redirect to indexer grep for PageRank-ranked results
  deny "Use \`indexer grep \"$PATTERN\"\` instead — it returns the same matches but ranked by file importance (PageRank), so core modules appear before tests and fixtures. Supports --ext, --ignore-case, --file-pattern, --max-results."
fi

# --- GLOB HANDLING ---
# All Glob calls should use indexer find/tree/map instead.
if [ "$TOOL_NAME" = "Glob" ]; then
  GLOB_PATTERN=$(echo "$INPUT" | jq -r '.tool_input.pattern')

  # Broad exploration patterns get a richer suggestion
  IS_BROAD=false
  if echo "$GLOB_PATTERN" | grep -qE '^\*\*/\*(\.(py|go|ts|tsx|js|jsx|rs|java|rb|c|cpp|h|hpp|cs))?$'; then
    IS_BROAD=true
  fi
  if echo "$GLOB_PATTERN" | grep -qE '^\*\*/\*\.\{[a-z,]+\}$'; then
    IS_BROAD=true
  fi

  if [ "$IS_BROAD" = true ]; then
    deny "Use \`indexer map --tokens 2048\` for a ranked repo overview, \`indexer find \"$GLOB_PATTERN\"\` to find files by pattern, or \`indexer tree\` for directory structure."
  fi

  # All other Glob patterns
  deny "Use \`indexer find \"$GLOB_PATTERN\"\` instead — it searches the index without a filesystem walk. Use \`indexer tree\` for directory structure."
fi

# --- BASH HANDLING ---
# Catch common shell commands that indexer replaces.
if [ "$TOOL_NAME" = "Bash" ]; then
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command')

  # Strip leading whitespace/env vars for matching
  CLEAN_CMD=$(echo "$CMD" | sed 's/^[[:space:]]*//')

  # find commands for file discovery
  if echo "$CLEAN_CMD" | grep -qE '^find\s'; then
    deny "Use \`indexer find <pattern>\` instead of \`find\` — it searches the index and respects ignore/allow patterns. Use \`indexer tree [path] --depth N\` for directory listings."
  fi

  # ls -R or ls for directory exploration
  if echo "$CLEAN_CMD" | grep -qE '^ls\s+(-[a-zA-Z]*R|-[a-zA-Z]*l[a-zA-Z]*R|.*-R)'; then
    deny "Use \`indexer tree [path] --depth N\` instead of \`ls -R\` — it shows the indexed project structure."
  fi

  # grep/rg for code search
  if echo "$CLEAN_CMD" | grep -qE '^(grep|rg|egrep|fgrep)\s'; then
    deny "Use \`indexer grep <pattern>\` instead — it returns matches ranked by file importance (PageRank). For symbol-level queries, use \`indexer search\`, \`indexer refs\`, or \`indexer callers\`."
  fi

  # cat/head/tail on source files to understand structure (not for small reads)
  if echo "$CLEAN_CMD" | grep -qE '^cat\s' && echo "$CLEAN_CMD" | grep -qE '\.(py|go|ts|tsx|js|jsx|rs|java|rb|c|cpp|cc|cxx|hpp|h|cs)(\s|$)'; then
    deny "Use \`indexer skeleton <file>\` to understand file structure (~10% of tokens). Use \`indexer impl <symbol>\` to read a specific function. Use Read only when you know the exact lines to edit."
  fi
fi

# Default: no intervention
echo '{}'
exit 0
