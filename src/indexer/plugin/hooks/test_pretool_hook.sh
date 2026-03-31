#!/usr/bin/env bash
# Tests for pretool-indexer-hint.sh
# Run: bash plugin/hooks/test_pretool_hook.sh

set -euo pipefail

HOOK="$(dirname "$0")/pretool-indexer-hint.sh"
PASS=0
FAIL=0

# Helper: feed JSON to the hook and check the decision
assert_denied() {
  local desc="$1" tool="$2" input_key="$3" input_val="$4"
  local json
  json=$(jq -n --arg t "$tool" --arg v "$input_val" \
    '{tool_name: $t, tool_input: {($input_key): $v}}' --arg input_key "$input_key")
  local result
  result=$(echo "$json" | bash "$HOOK")
  local decision
  decision=$(echo "$result" | jq -r '.hookSpecificOutput.permissionDecision // empty')
  if [ "$decision" = "deny" ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    echo "FAIL (expected deny): $desc  -> $result"
  fi
}

assert_allowed() {
  local desc="$1" tool="$2" input_key="$3" input_val="$4"
  local json
  json=$(jq -n --arg t "$tool" --arg v "$input_val" \
    '{tool_name: $t, tool_input: {($input_key): $v}}' --arg input_key "$input_key")
  local result
  result=$(echo "$json" | bash "$HOOK")
  local decision
  decision=$(echo "$result" | jq -r '.hookSpecificOutput.permissionDecision // empty')
  if [ -z "$decision" ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    echo "FAIL (expected allow): $desc  -> $result"
  fi
}

# Helper for checking the reason mentions a specific command
assert_denied_with() {
  local desc="$1" tool="$2" input_key="$3" input_val="$4" expected_cmd="$5"
  local json
  json=$(jq -n --arg t "$tool" --arg v "$input_val" \
    '{tool_name: $t, tool_input: {($input_key): $v}}' --arg input_key "$input_key")
  local result
  result=$(echo "$json" | bash "$HOOK")
  local decision reason
  decision=$(echo "$result" | jq -r '.hookSpecificOutput.permissionDecision // empty')
  reason=$(echo "$result" | jq -r '.hookSpecificOutput.permissionDecisionReason // empty')
  if [ "$decision" = "deny" ] && echo "$reason" | grep -qF "$expected_cmd"; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    echo "FAIL (expected deny with '$expected_cmd'): $desc  -> $result"
  fi
}

echo "=== Grep: symbol patterns → indexer search/refs/callers ==="
assert_denied_with "snake_case"            Grep pattern "my_func"           "indexer search"
assert_denied_with "leading underscore"    Grep pattern "_private_func"     "indexer search"
assert_denied_with "dunder"                Grep pattern "__init__"          "indexer search"
assert_denied_with "camelCase"             Grep pattern "handleRequest"     "indexer search"
assert_denied_with "react hook"            Grep pattern "useState"          "indexer search"
assert_denied_with "PascalCase"            Grep pattern "Database"          "indexer search"
assert_denied_with "Go exported"           Grep pattern "HTTPServer"        "indexer search"
assert_denied_with "SCREAMING_SNAKE"       Grep pattern "DEFAULT_IGNORE"    "indexer search"
assert_denied_with "dollar prefix"         Grep pattern '$scope'            "indexer search"

echo ""
echo "=== Grep: non-symbol patterns → indexer grep ==="
assert_denied_with "text with spaces"      Grep pattern "error handling"    "indexer grep"
assert_denied_with "regex pattern"          Grep pattern "TODO.*fix"        "indexer grep"
assert_denied_with "simple word"            Grep pattern "config"           "indexer grep"
assert_denied_with "short word"             Grep pattern "io"               "indexer grep"
assert_denied_with "keyword"               Grep pattern "the"              "indexer grep"
assert_denied_with "upper short"            Grep pattern "OK"               "indexer grep"
assert_denied_with "regex class"            Grep pattern "log\\[error\\]"   "indexer grep"

echo ""
echo "=== LSP (displays as Search) → indexer search/refs/callers ==="
assert_denied_with "lsp symbol"             LSP pattern "def _resolve_references"     "indexer search"
assert_denied_with "lsp class"              LSP pattern "Database"                    "indexer search"
assert_denied_with "lsp camelCase"          LSP pattern "handleRequest"               "indexer search"

echo ""
echo "=== Grep: wrong tool name → no intervention ==="
assert_allowed "Read tool"                  Read pattern "handleRequest"

echo ""
echo "=== Glob: broad patterns → indexer map/find/tree ==="
assert_denied_with "all python"             Glob pattern "**/*.py"           "indexer map"
assert_denied_with "all go"                 Glob pattern "**/*.go"           "indexer map"
assert_denied_with "all typescript"         Glob pattern "**/*.ts"           "indexer map"
assert_denied_with "catch-all"              Glob pattern "**/*"              "indexer map"
assert_denied_with "brace expansion"        Glob pattern "**/*.{ts,tsx}"     "indexer map"

echo ""
echo "=== Glob: specific patterns → indexer find ==="
assert_denied_with "specific dir"           Glob pattern "src/**/*.py"       "indexer find"
assert_denied_with "config files"           Glob pattern "**/config.*"       "indexer find"
assert_denied_with "specific file"          Glob pattern "**/README.md"      "indexer find"
assert_denied_with "docs"                   Glob pattern "docs/*.md"         "indexer find"

echo ""
echo "=== Glob: wrong tool name → no intervention ==="
assert_allowed "Read tool with glob"        Read pattern "**/*.py"

echo ""
echo "=== Bash: find → indexer find ==="
assert_denied_with "find files"             Bash command "find . -name '*.py'"          "indexer find"
assert_denied_with "find type f"            Bash command "find . -type f -name '*.go'"  "indexer find"
assert_denied_with "find recursive"         Bash command "find src/ -name 'test_*'"     "indexer find"

echo ""
echo "=== Bash: ls -R → indexer tree ==="
assert_denied_with "ls recursive"           Bash command "ls -R src/"                   "indexer tree"
assert_denied_with "ls long recursive"      Bash command "ls -lR"                       "indexer tree"
assert_denied_with "ls flags mixed"         Bash command "ls -alR src/"                 "indexer tree"

echo ""
echo "=== Bash: grep/rg → indexer grep ==="
assert_denied_with "shell grep"             Bash command "grep -r 'TODO' src/"          "indexer grep"
assert_denied_with "ripgrep"                Bash command "rg 'config' --type py"        "indexer grep"
assert_denied_with "egrep"                  Bash command "egrep 'func|class' *.py"      "indexer grep"

echo ""
echo "=== Bash: cat source files → indexer skeleton ==="
assert_denied_with "cat python"             Bash command "cat src/main.py"              "indexer skeleton"
assert_denied_with "cat typescript"         Bash command "cat src/app.ts"               "indexer skeleton"
assert_denied_with "cat go"                 Bash command "cat cmd/server.go"            "indexer skeleton"
assert_denied_with "cat rust"               Bash command "cat src/lib.rs"               "indexer skeleton"
assert_denied_with "cat java"               Bash command "cat App.java"                 "indexer skeleton"

echo ""
echo "=== Bash: should NOT block ==="
assert_allowed "git status"                 Bash command "git status"
assert_allowed "git diff"                   Bash command "git diff"
assert_allowed "npm install"                Bash command "npm install"
assert_allowed "python run"                 Bash command "python3 main.py"
assert_allowed "pytest"                     Bash command "pytest tests/"
assert_allowed "indexer command"            Bash command "indexer search MyClass"
assert_allowed "indexer grep"              Bash command "indexer grep TODO"
assert_allowed "cat non-code"               Bash command "cat README.md"
assert_allowed "cat json"                   Bash command "cat package.json"
assert_allowed "ls simple"                  Bash command "ls src/"
assert_allowed "mkdir"                      Bash command "mkdir -p src/utils"
assert_allowed "echo"                       Bash command "echo hello"

echo ""
echo "=============================="
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && echo "All tests passed!" || exit 1
