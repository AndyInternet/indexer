---
name: index-codebase
description: Build or update the structural code index for the current project using the indexer CLI. Use when the user explicitly asks to index or re-index the codebase, or to force a full rebuild.
disable-model-invocation: true
---

# Index Codebase

Build or incrementally update the structural code index for the current project.

Note: The index is automatically built on first query and auto-updated on every query when the fingerprint changes (git HEAD, working tree status, or config changes). Non-git repos use file mtime fingerprinting. This skill is for explicit/forced indexing.

## Steps

1. Run the indexer. It will auto-detect whether to init or update:

```bash
indexer update .
```

2. After indexing completes, show the user what was indexed:

```bash
indexer stats
```

3. Print a brief repo map so the user can see the top-ranked files:

```bash
indexer map --tokens 1024
```

## If indexer is not installed

If the `indexer` command is not found, tell the user to install it globally:

```bash
uv tool install indexer
```

Then suggest they also run `/setup-indexer` to configure Claude to prefer the index for codebase navigation.
