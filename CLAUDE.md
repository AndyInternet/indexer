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

1. **Scanner** ([scanner.py](src/indexer/scanner.py)) walks the filesystem, respects `.gitignore` + built-in ignore patterns (via `pathspec`), and SHA-256 hashes each file for change detection.

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
- **Auto-freshness**: Every query command checks stored git branch/commit against current HEAD. If stale (branch switch, new commits), an incremental update runs automatically. If no index exists, it's built on first use. This is handled by [freshness.py](src/indexer/freshness.py). Non-git repos skip the check gracefully.

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

> **Use `indexer` commands via Bash for ALL code navigation in this repo. Available commands: `indexer search <name>`, `indexer refs <symbol>`, `indexer callers <symbol>`, `indexer impl <symbol>`, `indexer skeleton [file]`, `indexer map --tokens 2048`, `indexer grep <pattern> [--ext .yaml] [-i]`, `indexer find <pattern>`, `indexer tree [path]`. Do NOT use Grep, Glob, find, or ls. Use `indexer grep` for text search, `indexer find` for file search, `indexer tree` for directory listing. Only use Read when you know the exact file and lines to edit.**

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
