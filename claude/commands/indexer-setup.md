# Setup Indexer for This Project

Configure the current project so Claude prefers `indexer` commands over grep/glob for codebase navigation in all future sessions.

## Steps

1. Check if a `CLAUDE.md` exists in the project root. If it does, read it so you can append without overwriting existing content.

2. Append the following section to `CLAUDE.md` (create the file if it doesn't exist). Add a blank line separator if the file already has content:

````markdown
## Codebase Navigation — Indexer (MANDATORY)

**CRITICAL: You MUST use `indexer` commands (via Bash) instead of Grep, Glob, Read, find, or ls for ALL code navigation. This is not optional. Violations waste tokens and miss cross-file relationships that only the index captures.**

### Default workflow — follow this order

1. **Orient first**: Run `indexer map --tokens 2048` to understand what matters in the repo. **When you already know which files are relevant** (e.g., the user mentioned a file, you're mid-task, or the question is about a specific area), add `--focus <file>` for each relevant file — this applies a 50x PageRank boost so the map centers on that part of the codebase. Multiple `--focus` flags are supported.
2. **Find symbols**: Run `indexer search <name>` — NEVER grep for function/class/method/type definitions.
3. **Trace usage**: Run `indexer refs <symbol>` or `indexer callers <symbol>` — NEVER grep for a function name to find who calls it or imports it.
4. **Understand structure**: Run `indexer skeleton <file>` — NEVER read an entire file just to see its structure.
5. **Get implementation**: Run `indexer impl <symbol>` to see full source of a specific symbol.
6. **Read to edit**: Use `Read` ONLY when you already know the exact file and lines you need to modify.

### Exceptions — ONLY these justify Grep/Glob/Read

| Situation | Why indexer can't help | What to use |
|---|---|---|
| Reading a specific file to edit it | You need exact file contents | Read |
| `indexer` command unavailable | Tool missing | Grep/Glob/Read as fallback |

**Note:** `indexer grep` now covers full-text search across all indexed files (including non-code: YAML, Makefile, Dockerfile, etc.). Use `indexer grep` instead of Grep for searching file contents. Use `indexer find` instead of Glob/find for locating files. Use `indexer tree` instead of ls/find for directory exploration.

**If your reason is not in this table, use indexer.** "I want to find where function X is defined" is NOT an exception — use `indexer search X`.

### Anti-patterns — stop and correct yourself

| WRONG | RIGHT |
|---|---|
| `grep -r "ExecuteGenerateFlow"` to find definition | `indexer search ExecuteGenerateFlow` |
| `grep -r "import.*services/ai"` to find importers | `indexer refs ai` or `indexer callers <symbol>` |
| `find . -name "*.go" -type f` to explore repo | `indexer find "*.go"` or `indexer map --tokens 2048` |
| `Read` entire `main.go` to understand structure | `indexer skeleton main.go` |
| `grep -r "InitializeGenkit"` to find callers | `indexer callers InitializeGenkit` |
| `Glob **/*.py` to find Python files | `indexer find "*.py"` |
| `grep -r "genkit" *.yaml` to search config files | `indexer grep "genkit" --ext .yaml` |
| `ls -R src/` to see directory structure | `indexer tree src` |

### When spawning agents

Agents do NOT inherit these instructions. You MUST include this directive in every agent prompt:

> **Use `indexer` commands via Bash for ALL code navigation in this repo. Available commands: `indexer search <name>`, `indexer refs <symbol>`, `indexer callers <symbol>`, `indexer impl <symbol>`, `indexer skeleton [file]`, `indexer map --tokens 2048`, `indexer grep <pattern> [--ext .yaml] [-i]`, `indexer find <pattern>`, `indexer tree [path]`, `indexer config show|reset|ignore|allow|remove`. Do NOT use Grep, Glob, find, or ls. Use `indexer grep` for text search, `indexer find` for file search, `indexer tree` for directory listing. Only use Read when you know the exact file and lines to edit.**

Copy this block verbatim into agent prompts. Do not paraphrase or abbreviate it.

### Quick reference

| Task | Command |
|---|---|
| Ranked repo overview | `indexer map --tokens 2048` |
| Focused repo map | `indexer map --tokens 1024 --focus <file>` |
| Find a symbol | `indexer search <name>` |
| Find references | `indexer refs <symbol>` |
| Find callers | `indexer callers <symbol>` |
| Get implementation | `indexer impl <symbol>` |
| File skeleton | `indexer skeleton <file>` |
| Full repo skeleton | `indexer skeleton` |
| Full-text search | `indexer grep <pattern> [--ext .yaml] [-i]` |
| Find files by name | `indexer find <pattern> [--type f\|d]` |
| Directory tree | `indexer tree [path] [--depth N]` |
| Index stats | `indexer stats` |
| View config | `indexer config show` |
| Reset config to defaults | `indexer config reset` |
| Add ignore pattern | `indexer config ignore <pattern>` |
| Add allow pattern (overrides ignore) | `indexer config allow <pattern>` |
| Remove ignore/allow pattern | `indexer config remove <pattern>` |
````

3. Install the PreToolUse hook that reminds agents to use indexer:

   a. Create the directory `.claude/hooks/` if it doesn't exist.

   b. Create `.claude/hooks/pretool-indexer-hint.sh` with the hook script from the indexer repository. This script:
      - Detects when Grep is used with symbol-like patterns (CamelCase, snake_case, PascalCase, ALL_CAPS)
      - Detects when Glob is used for broad code exploration (`**/*.py`, `**/*`, etc.)
      - Injects `additionalContext` reminding to use indexer commands
      - Never blocks — only adds helpful reminders

   c. Make it executable: `chmod +x .claude/hooks/pretool-indexer-hint.sh`

   d. Create or update `.claude/settings.json` to register the hook and allow-list all indexer commands (they are read-only and non-destructive):
   ```json
   {
     "permissions": {
       "allow": [
         "Bash(indexer map:*)",
         "Bash(indexer search:*)",
         "Bash(indexer refs:*)",
         "Bash(indexer callers:*)",
         "Bash(indexer impl:*)",
         "Bash(indexer skeleton:*)",
         "Bash(indexer grep:*)",
         "Bash(indexer find:*)",
         "Bash(indexer tree:*)",
         "Bash(indexer stats:*)",
         "Bash(indexer init:*)",
         "Bash(indexer update:*)",
         "Bash(indexer config:*)",
         "Bash(indexer --help:*)"
       ]
     },
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Grep|Glob",
           "hooks": [
             {
               "type": "command",
               "command": "bash .claude/hooks/pretool-indexer-hint.sh"
             }
           ]
         }
       ]
     }
   }
   ```
   If `.claude/settings.json` already exists, merge the `permissions.allow` and `hooks` keys — do not overwrite other settings.

4. Tell the user:
   - CLAUDE.md has been updated with comprehensive indexer instructions
   - A PreToolUse hook has been installed to remind agents about indexer commands
   - Claude will now prefer `indexer` commands over grep/glob in this project
   - The index will be built automatically on first use (no manual `indexer init` needed)
   - The index auto-updates on every query when the fingerprint changes (git HEAD, working tree status, or `.indexer/config.json` changes). Non-git repos use file mtime fingerprinting instead.
