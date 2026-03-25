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
## Codebase Navigation — Indexer

This project has a structural code index at `.indexer/index.db` built with the `indexer` CLI tool. **Always prefer indexer commands over grep/glob/find for navigating this codebase.** The index uses Tree-sitter AST parsing, code skeletons, and PageRank to provide highly optimized context with minimal token usage.

### Preferred workflow

1. **Start of session**: Run `indexer update .` to refresh the index if files have changed.

2. **Understand the codebase structure**: Use `indexer map --tokens 2048` to get a PageRank-ranked overview of the most important files and their key symbols. Use `--focus <file>` to boost files relevant to the current task.

3. **Find symbols**: Use `indexer search <name>` to find function, class, or method definitions by name. This is faster and more precise than grep for finding definitions.

4. **Understand dependencies**: Use `indexer refs <symbol>` or `indexer callers <symbol>` to trace how symbols are used across the codebase. This replaces multi-step grep workflows.

5. **Read specific implementations**: Use `indexer impl <symbol>` to get the exact source code of a function or class, with line numbers. This retrieves only the relevant code, not the entire file.

6. **Get file overviews**: Use `indexer skeleton <file>` to see the structural outline of a file (imports, class definitions, function signatures) without implementation bodies. This uses ~10% of the tokens compared to reading the full file.

### When to fall back to grep/glob

- The index hasn't been built yet (run `indexer init .` first)
- Searching for string literals, comments, or non-symbol text patterns
- Searching within file contents that aren't structural code (config files, prose, etc.)
- The `indexer` command is not available

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
