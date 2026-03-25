# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development

```bash
# Install for development (editable)
uv pip install -e ".[dev]"

# Install globally as a CLI tool
uv tool install /path/to/indexer

# Run the CLI
indexer init .          # Build index from scratch
indexer update .        # Incremental update
indexer stats           # Show index statistics

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

1. **Scanner** ([scanner.py](src/indexer/scanner.py)) walks the filesystem, respects `.gitignore` + built-in ignore patterns (via `pathspec`), and SHA-256 hashes each file for change detection.

2. **Parser** ([parsing/](src/indexer/parsing/)) uses Tree-sitter to produce ASTs. Language detection is extension-based ([languages.py](src/indexer/parsing/languages.py)). Symbol and reference extraction ([extractors.py](src/indexer/parsing/extractors.py)) walks AST nodes to find definitions and cross-file identifier usage.

3. **Skeleton extractor** ([skeleton/extractor.py](src/indexer/skeleton/extractor.py)) strips function/method bodies from parsed ASTs, keeping only imports, signatures, and class structure (~10% of original tokens).

4. **Database** ([db.py](src/indexer/db.py)) is SQLite with WAL mode. Four tables: `files`, `symbols`, `refs`, `skeletons`. All child tables use `ON DELETE CASCADE` from `files`, so re-indexing a file automatically cleans up stale data. Data classes (`FileRecord`, `SymbolRecord`, `RefRecord`) are plain dataclasses, not ORM models.

5. **Graph + PageRank** ([graph/](src/indexer/graph/)) builds a networkx `DiGraph` from cross-file references (file A references symbol in file B = edge A→B). PageRank is a custom power-iteration implementation ([pagerank.py](src/indexer/graph/pagerank.py)) with no scipy dependency. `--focus` applies a 50x personalization boost.

6. **Repo map renderer** ([graph/repomap.py](src/indexer/graph/repomap.py)) uses binary search to fit the maximum number of PageRank-ranked files/symbols within a token budget. Token counting uses tiktoken's `cl100k_base` encoding.

7. **CLI** ([cli.py](src/indexer/cli.py)) is the Click entry point. The two-pass indexing pattern is important: `_index_files` extracts symbols first, then `_resolve_references` runs a second pass to match identifier usage against the now-complete symbol table.

## Key Design Decisions

- **Two-pass indexing**: References can only be resolved after all symbols from all files are in the database. The CLI orchestrates this as: index all files (pass 1), then resolve all references (pass 2).
- **No scipy/numpy**: PageRank uses pure-Python power iteration to keep the dependency footprint small for global CLI installation.
- **Self-ignoring `.indexer/`**: The `Database.connect()` method auto-creates a `.indexer/.gitignore` containing `*`, so the index directory is ignored even without project-level `.gitignore` configuration.

## Codebase Navigation — Indexer

This project has a structural code index at `.indexer/index.db`. **Always prefer indexer commands over grep/glob/find for navigating this codebase.**

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

### When to fall back to grep/glob

- Searching for string literals, comments, or non-symbol text patterns
- Searching within non-structural content (config files, prose)
- The `indexer` command is not available
