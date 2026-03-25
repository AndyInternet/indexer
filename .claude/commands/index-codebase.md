Run the indexer on the current codebase to build or update the structural code index.

First, check if an index already exists:

```bash
ls .indexer/index.db 2>/dev/null
```

If the index exists, run an incremental update:

```bash
indexer update .
```

If no index exists, create one from scratch:

```bash
indexer init .
```

After indexing completes, run `indexer stats` to show the user what was indexed.

Then print a brief repo map so the user can see the top-ranked files:

```bash
indexer map --tokens 1024
```

If the `indexer` command is not found, tell the user to install it globally with:

```
uv tool install /path/to/indexer
```

or if they have the indexer project locally, they can run it with:

```
uv run --from /path/to/indexer indexer init .
```
