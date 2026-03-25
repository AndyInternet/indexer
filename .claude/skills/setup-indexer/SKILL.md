---
name: setup-indexer
description: Configure this project so Claude prefers the indexer for codebase navigation over grep and glob. Adds usage instructions to CLAUDE.md and ensures the index directory is gitignored.
disable-model-invocation: true
---

# Setup Indexer for This Project

Configure the current project so Claude prefers `indexer` commands over grep/glob for codebase navigation in all future sessions.

## Steps

1. Check if a `CLAUDE.md` exists in the project root. If it does, read it so you can append without overwriting existing content.

2. Append the following section to `CLAUDE.md` (create the file if it doesn't exist). Add a blank line separator if the file already has content:

```markdown
## Codebase Navigation — Indexer (MANDATORY)

**CRITICAL: You MUST use `indexer` commands instead of Grep, Glob, Read, find, or ls for code navigation. Do NOT use Grep/Glob/Read tools to explore code structure, find symbol definitions, trace callers, or understand file layouts.**

The only exceptions where Grep/Glob/Read are acceptable:
- The index hasn't been built (run `indexer init .` first)
- Searching for string literals, comments, or non-code text patterns
- Reading specific file contents you already know you need (e.g., reading a config file, reading a file to edit it)
- The `indexer` command is not available

**Self-check**: If you are about to grep for a function/class/symbol definition, STOP and use `indexer search` instead. If you are about to read a whole file to understand its structure, use `indexer skeleton` instead. If you need to trace callers or references, use `indexer callers`/`indexer refs` instead of grepping for the function name.

**When spawning agents**: Always instruct agents to use `indexer` commands via Bash for code exploration. Agents do not automatically follow these instructions unless explicitly told.

### Quick reference

| Task | Command |
|---|---|
| Refresh index | `indexer update .` |
| Ranked repo overview | `indexer map --tokens 2048` |
| Focused repo map | `indexer map --tokens 1024 --focus <file>` |
| Find a symbol | `indexer search <name>` |
| Find references | `indexer refs <symbol>` |
| Find callers | `indexer callers <symbol>` |
| Get implementation | `indexer impl <symbol>` |
| File skeleton | `indexer skeleton <file>` |
| Full repo skeleton | `indexer skeleton` |
| Index stats | `indexer stats` |
```

3. Check if `.indexer/` is in the project's `.gitignore`. If not, append it:

```bash
grep -q '\.indexer' .gitignore 2>/dev/null || echo '.indexer/' >> .gitignore
```

4. Tell the user:
   - CLAUDE.md has been updated with indexer instructions
   - Claude will now prefer `indexer` commands over grep/glob in this project
   - They should run `/index-codebase` (or `indexer init .`) to build the index if it doesn't exist yet
