---
name: index-codebase
description: Build or update the structural code index for the current project using the indexer CLI. Use when starting a coding session, when the user asks to index or re-index the codebase, or before performing codebase-wide searches.
disable-model-invocation: true
---

# Index Codebase

Build or incrementally update the structural code index for the current project.

## Steps

1. Check if an index already exists:

```bash
ls .indexer/index.db 2>/dev/null
```

2. If the index exists, run an incremental update (only re-parses changed files):

```bash
indexer update .
```

3. If no index exists, create one from scratch:

```bash
indexer init .
```

4. After indexing completes, show the user what was indexed:

```bash
indexer stats
```

5. Print a brief repo map so the user can see the top-ranked files:

```bash
indexer map --tokens 1024
```

## If indexer is not installed

If the `indexer` command is not found, tell the user to install it globally:

```bash
uv tool install indexer
```

Then suggest they also run `/setup-indexer` to configure Claude to prefer the index for codebase navigation.
