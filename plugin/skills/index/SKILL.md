---
name: index
description: Build or incrementally update the structural code index for the current project. Rarely needed — queries auto-update.
argument-hint: ""
---

# Index Codebase

Build or incrementally update the structural code index for the current project.

Note: The index is automatically built on first query and auto-updated on every query when the fingerprint changes (git HEAD, working tree status, or config changes). Non-git repos use file mtime fingerprinting. This command is for explicit/forced indexing.

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

If the `indexer` command is not found, tell the user to install it:

```bash
uv tool install indexer
```

Or from a local clone:

```bash
uv tool install /path/to/indexer
```
