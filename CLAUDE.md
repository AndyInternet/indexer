# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development

```bash
# Install for development (editable)
uv pip install -e ".[dev]"

# Install globally as a CLI tool
uv tool install /path/to/indexer

# Run the CLI (index is auto-built and auto-updated on first use)
indexer stats           # Show index statistics
indexer init .          # Force full re-index from scratch
indexer update .        # Explicit incremental update

# Lint
ruff check src/
ruff format --check src/

# Run tests
pytest
pytest tests/test_specific.py       # Single file
pytest tests/test_specific.py::test_name  # Single test
```

## Architecture

The indexing pipeline flows: **scan -> parse -> extract -> store -> rank -> render**.

1. **Scanner** ([scanner.py](src/indexer/scanner.py)) walks the filesystem, respects `.gitignore` + configurable ignore/allow patterns (via `pathspec`), and SHA-256 hashes each file for change detection. Allow patterns override ignore patterns, enabling selective inclusion of paths inside otherwise-ignored directories.

0. **Config** ([config.py](src/indexer/config.py)) manages `.indexer/config.json`, the sole source of truth for ignore and allow patterns. On first use, the config file is seeded with sensible defaults. The `Config` dataclass exposes `ignore_patterns` (always includes `.git` and `.indexer` as safety invariants) and `allow_patterns`. Config changes are detected by the freshness system — the fingerprint includes a hash of `config.json`, so query commands auto-trigger re-indexing when config changes.

2. **Parser** ([parsing/](src/indexer/parsing/)) uses Tree-sitter to produce ASTs. Language detection is extension-based ([languages.py](src/indexer/parsing/languages.py)). Symbol and reference extraction ([extractors.py](src/indexer/parsing/extractors.py)) walks AST nodes to find definitions and cross-file identifier usage.

3. **Skeleton extractor** ([skeleton/extractor.py](src/indexer/skeleton/extractor.py)) strips function/method bodies from parsed ASTs, keeping only imports, signatures, and class structure (~10% of original tokens).

4. **Database** ([db.py](src/indexer/db.py)) is SQLite with WAL mode. Five tables: `files`, `symbols`, `refs`, `skeletons`, `metadata`. All child tables use `ON DELETE CASCADE` from `files`, so re-indexing a file automatically cleans up stale data. The `metadata` table stores git branch/commit for freshness tracking. Data classes (`FileRecord`, `SymbolRecord`, `RefRecord`) are plain dataclasses, not ORM models.

5. **Graph + PageRank** ([graph/](src/indexer/graph/)) builds a networkx `DiGraph` from cross-file references (file A references symbol in file B = edge A→B). PageRank is a custom power-iteration implementation ([pagerank.py](src/indexer/graph/pagerank.py)) with no scipy dependency. `--focus` applies a 50x personalization boost.

6. **Repo map renderer** ([graph/repomap.py](src/indexer/graph/repomap.py)) uses binary search to fit the maximum number of PageRank-ranked files/symbols within a token budget. Token counting uses tiktoken's `cl100k_base` encoding.

7. **CLI** ([cli.py](src/indexer/cli.py)) is the Click entry point. The two-pass indexing pattern is important: `_index_files` extracts symbols first, then `_resolve_references` runs a second pass to match identifier usage against the now-complete symbol table.

## Key Design Decisions

- **Two-pass indexing**: References can only be resolved after all symbols from all files are in the database. The CLI orchestrates this as: index all files (pass 1), then resolve all references (pass 2).
- **No scipy/numpy**: PageRank uses pure-Python power iteration to keep the dependency footprint small for global CLI installation.
- **Self-ignoring `.indexer/`**: The `Database.connect()` method auto-creates a `.indexer/.gitignore` containing `*`, so the index directory is ignored even without project-level `.gitignore` configuration.
- **Auto-freshness**: Every query command computes a fingerprint — `sha256(HEAD + git status --porcelain + config.json hash)` for git repos, or `sha256(sorted file mtimes + config.json hash)` for non-git repos — and compares it against the stored fingerprint. If they differ, an incremental update runs automatically. If no index exists, it's built on first use. This is handled by [freshness.py](src/indexer/freshness.py). There is no TTL — staleness is detected purely by fingerprint mismatch.
- **Persistent config**: Ignore/allow patterns live in `.indexer/config.json`, not hardcoded. The `_SEED_IGNORE` list in `config.py` only seeds new config files — once the file exists, it is the sole source of truth. Allow patterns use the same gitignore glob syntax and override ignore patterns, with smart directory descent (only enters ignored directories far enough to reach allowed subtrees).
