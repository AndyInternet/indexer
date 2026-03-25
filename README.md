# Indexer

AI-optimized codebase index generator. Uses Tree-sitter AST parsing, code skeleton extraction, and PageRank-based repo mapping to give AI coding agents surgical precision when navigating code — reducing token consumption by up to 90%.

Built from research on [advanced codebase indexing strategies for AI agents](research.md).

## Why

AI coding agents waste massive amounts of tokens using naive `grep`/`glob` to navigate codebases. Benchmarks show agents can burn 117,000+ tokens just *finding* the right files. With structural indexing, the same lookup costs ~8,500 tokens — a 14x reduction.

Indexer solves this by generating a local SQLite index of your codebase containing:

- **Code skeletons** — imports + function signatures + class structure, no bodies (~10% of original tokens)
- **PageRank repo map** — dependency-graph-ranked overview of the most important files, fitted to a configurable token budget
- **Symbol index** — searchable database of all definitions and cross-file references
- **Incremental updates** — SHA-256 hashing means only changed files are re-parsed

## Quickstart

### Install globally

```bash
# Install with uv (recommended)
uv tool install /path/to/indexer

# Or with pip
pip install /path/to/indexer
```

Once installed, `indexer` is available as a command anywhere on your system.

### Index a codebase

```bash
cd /path/to/your/project
indexer init .
```

This scans the project, parses all supported source files with Tree-sitter, extracts symbols and references, generates code skeletons, and stores everything in `.indexer/index.db`.

### Query the index

```bash
# Repo map — PageRank-ranked overview within a token budget
indexer map --tokens 2048

# Repo map focused on files you're editing (50x boost)
indexer map --tokens 1024 --focus src/auth/handler.py --focus src/db/models.py

# Code skeleton — signatures only, no implementation bodies
indexer skeleton src/auth/handler.py

# Full repo skeleton
indexer skeleton

# Search symbols by name
indexer search authenticate

# Find all references to a symbol
indexer refs DatabaseConnection

# Find all callers of a function
indexer callers validate_token

# Get the full implementation of a specific symbol
indexer impl parse_file

# Show index statistics
indexer stats

# Incrementally update after code changes
indexer update
```

## Commands Reference

| Command | Description |
|---|---|
| `indexer init [path]` | Index a codebase. Creates `.indexer/index.db` in the project root. |
| `indexer update [path]` | Incrementally re-index only changed files (based on SHA-256 hash comparison). |
| `indexer skeleton [file]` | Print code skeleton of a single file or the entire repo. Strips function bodies, keeps imports, signatures, class structure. |
| `indexer map [--tokens N] [--focus FILE]` | Print a PageRank-ranked repo map within a token budget (default: 4096). Use `--focus` to boost specific files. Repeatable. |
| `indexer search <query>` | Search symbol definitions by name. Supports partial matches. |
| `indexer refs <symbol>` | Find all files and lines that reference a symbol. |
| `indexer callers <symbol>` | Find all files that call a function, grouped by file with line numbers. |
| `indexer impl <symbol>` | Print the full source code of a specific symbol, with line numbers. |
| `indexer stats` | Show index statistics: file count, symbol count, reference count, language breakdown. |

## Supported Languages

| Language | Extensions |
|---|---|
| Python | `.py` |
| TypeScript | `.ts`, `.tsx` |
| JavaScript | `.js`, `.jsx` |
| Go | `.go` |
| Rust | `.rs` |
| Java | `.java` |
| C | `.c`, `.h` |
| C++ | `.cpp`, `.cc`, `.cxx`, `.hpp` |
| Ruby | `.rb` |
| C# | `.cs` |

## How It Works

### 1. Tree-sitter AST Parsing

Every source file is parsed into a concrete syntax tree using [Tree-sitter](https://tree-sitter.github.io/). This gives the indexer deep structural understanding of the code — it sees functions, classes, methods, imports, and references as discrete nodes rather than lines of text.

### 2. Code Skeleton Extraction

For each parsed file, the indexer generates a "skeleton" that preserves the structural interface while stripping implementation:

```
# Original (45 lines, ~400 tokens)
class AuthHandler:
    def __init__(self, db: Database, secret: str):
        self._db = db
        self._secret = secret
        self._cache = {}
        self._setup_validators()

    def validate_token(self, token: str) -> bool:
        if not token:
            return False
        try:
            payload = jwt.decode(token, self._secret, algorithms=["HS256"])
            user = self._db.get_user(payload["sub"])
            return user is not None and not user.is_banned
        except jwt.InvalidTokenError:
            return False
    ...

# Skeleton (8 lines, ~50 tokens)
class AuthHandler:
    def __init__(self, db: Database, secret: str):
        ...
    def validate_token(self, token: str) -> bool:
        ...
    def refresh_session(self, session_id: str) -> Session:
        ...
    def revoke_token(self, token: str) -> None:
        ...
```

### 3. PageRank Repo Map

The indexer builds a directed dependency graph (file A references symbol defined in file B = edge A -> B) and runs personalized PageRank to determine which files are most architecturally important. The output is a token-budgeted, scope-aware view:

```
src/indexer/db.py:
⋮
  class Database:
⋮
    def connect(self) -> sqlite3.Connection
⋮
    def upsert_file(self, f: FileRecord) -> int
⋮
    def search_symbols(self, query: str) -> list[tuple[SymbolRecord, str]]

src/indexer/cli.py:
⋮
  def init(path: str)
⋮
  def repo_map(tokens: int, focus: tuple[str, ...], path: str)
```

The map uses binary search to fit the maximum number of ranked symbols within your token budget. Use `--focus` to boost files you're currently working on (50x PageRank multiplier).

### 4. Incremental Updates

Files are tracked by SHA-256 content hash. Running `indexer update` only re-parses files that actually changed. The SQLite database uses `ON DELETE CASCADE` so re-indexing a file automatically cleans up its stale symbols, references, and skeleton.

## Claude Code Integration

Indexer ships with two [Claude Code skills](https://code.claude.com/docs/en/skills) that can be installed globally so `/index-codebase` and `/setup-indexer` are available in any project.

### Install the skills

```bash
# Copy the skill directories to your global Claude skills folder
cp -r /path/to/indexer/.claude/skills/index-codebase ~/.claude/skills/
cp -r /path/to/indexer/.claude/skills/setup-indexer ~/.claude/skills/
```

### `/index-codebase`

Builds or incrementally updates the structural code index for the current project. Run this at the start of a coding session to ensure the index is fresh.

### `/setup-indexer`

Adds indexer usage instructions to the current project's `CLAUDE.md`, configuring Claude to prefer `indexer` commands over `grep`/`glob` for codebase navigation. Also ensures `.indexer/` is in `.gitignore`. Run this once per project.

### Recommended workflow

```
# In any project, one-time setup:
/setup-indexer
/index-codebase

# Start of each session:
/index-codebase
```

After setup, Claude will automatically use `indexer search`, `indexer map`, `indexer skeleton`, etc. instead of grep/glob when navigating the codebase.

## Configuration

The index is stored in `.indexer/index.db` inside the project root. The `.indexer/` directory includes its own `.gitignore` (containing `*`) so it self-ignores even if the project doesn't explicitly exclude it.

The following paths are ignored by default:

- Version control: `.git`
- Dependencies: `node_modules`, `.venv`, `venv`
- Build artifacts: `dist`, `build`, `*.pyc`, `*.so`, `*.o`, `*.class`
- Binary/media files: `*.png`, `*.jpg`, `*.pdf`, `*.woff2`, `*.zip`
- Lock files: `package-lock.json`, `yarn.lock`, `*.lock`
- Caches: `__pycache__`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`

The `.gitignore` in your project root is also respected.

## Architecture

```
src/indexer/
  cli.py              CLI entry point (Click)
  db.py               SQLite schema + CRUD (WAL mode, cascade deletes)
  scanner.py           File discovery, SHA-256 hashing, change detection
  config.py            Default ignore patterns, paths
  tokens.py            tiktoken wrapper (cl100k_base encoding)
  parsing/
    languages.py       Extension -> language map, parser cache
    parser.py          Tree-sitter parse wrapper
    extractors.py      Symbol + reference extraction from ASTs
  skeleton/
    extractor.py       Code skeleton generation (strip bodies, keep signatures)
  graph/
    builder.py         Build networkx DiGraph from cross-file references
    pagerank.py        Custom power-iteration PageRank (no scipy dependency)
    repomap.py         Token-budgeted, scope-aware repo map rendering
```

## License

MIT
