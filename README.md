# Indexer

AI-optimized codebase index generator. Uses Tree-sitter AST parsing, code skeleton extraction, and PageRank-based repo mapping to give AI coding agents surgical precision when navigating code — reducing token consumption by up to 90%.

Built from research on [advanced codebase indexing strategies for AI agents](research.md).

## Why This Instead of grep/find/ls

Standard bash tools are designed for humans. AI agents use them anyway and pay for it — in tokens, in missed context, and in wasted turns. Here's what indexer does differently:

| What agents do | The problem | What indexer does instead |
|---|---|---|
| `grep -r "MyClass"` to find a definition | Returns every mention — imports, comments, string literals, tests — and the agent has to read them all to find the actual definition | `indexer search MyClass` returns only the definition with file, line, signature |
| `grep -r "MyClass"` to find callers | Same wall of noise. Agent can't distinguish callers from definitions from type annotations | `indexer callers MyClass` returns only call sites, grouped by file |
| `cat main.py` to understand a file | Dumps 500 lines of implementation into context. Agent burns tokens reading function bodies it doesn't need | `indexer skeleton main.py` shows imports + signatures only (~10% of tokens) |
| `find . -name "*.py"` to explore the repo | Flat alphabetical list with no signal about what matters | `indexer map --tokens 2048` shows the most architecturally important files first, ranked by PageRank |
| `grep -r "config" *.yaml` to search configs | Results in filesystem order — test fixtures before core config | `indexer grep "config" --ext .yaml` ranks results by file importance |
| `find . -type f` / `ls -R` to see structure | Raw directory listing, no filtering for what the index knows about | `indexer tree --depth 2` shows the indexed project structure |

The core advantages:

- **Smarter results** — PageRank ranking surfaces the most important files first in `map`, `grep`, and `find`. An agent searching for `"database"` sees the core DB module before test mocks.
- **Structural understanding** — `search`, `refs`, and `callers` use the AST-parsed symbol index, not text matching. They know the difference between a function definition, a function call, and a comment mentioning the function name.
- **Token efficiency** — `skeleton` compresses files to ~10% of their token cost. `map` fits a ranked repo overview into a configurable token budget. Agents get more context per token spent.
- **Consistency** — All commands respect the same ignore patterns (`.gitignore` + built-in defaults). No accidental searches through `node_modules` or `.venv`.
- **Incremental** — SHA-256 content hashing means `indexer update` only re-parses changed files. The index stays fresh without full re-scans.

## What It Indexes

Indexer generates a local SQLite index of your codebase containing:

- **Code skeletons** — imports + function signatures + class structure, no bodies (~10% of original tokens)
- **PageRank repo map** — dependency-graph-ranked overview of the most important files, fitted to a configurable token budget
- **Symbol index** — searchable database of all definitions and cross-file references
- **Full-text search** — PageRank-ranked grep across all indexed files, so the most important results come first
- **File discovery** — find files by pattern and view directory trees from the index, no filesystem walk needed
- **Incremental updates** — SHA-256 hashing means only changed files are re-parsed

## Quickstart

### Install globally

```bash
# Install or upgrade everything (CLI tool + Claude skills) with one command
./install.sh

# Or install just the CLI tool manually
uv tool install /path/to/indexer

# Or with pip
pip install /path/to/indexer
```

Once installed, `indexer` is available as a command anywhere on your system. Running `install.sh` again upgrades both the CLI and skills in place.

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

# Full-text search, ranked by file importance
indexer grep "TODO" --ext .py
indexer grep "database" --ignore-case
indexer grep "config" --ext .yaml,.toml

# Find files by name (substring match by default)
indexer find "auth"
indexer find "*.py"
indexer find "test" --type f
indexer find "src" --type d

# Directory tree from indexed files
indexer tree
indexer tree src/indexer --depth 2

# Show index statistics
indexer stats

# Incrementally update after code changes
indexer update .
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
| `indexer grep <pattern>` | Full-text regex search across all indexed files, ranked by PageRank importance. Supports `--ext`, `--ignore-case`, `--file-pattern`, `--max-results`. |
| `indexer find <pattern>` | Find files or directories by name. Plain text does substring matching; glob characters (`*`, `?`, `[`) are used as-is. Use `--type f` for files only, `--type d` for directories only. |
| `indexer tree [path]` | Show directory tree built from indexed files. Use `--depth N` to limit depth. |
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

Note: `indexer grep`, `indexer find`, and `indexer tree` work on *all* indexed files regardless of language, including YAML, Markdown, Makefile, Dockerfile, config files, etc.

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

### 4. PageRank-Ranked Grep

Unlike traditional `grep` which returns results in file-system order, `indexer grep` sorts results by PageRank importance. When searching for `"config"` across 200 files, hits in your core configuration module appear before test fixtures. Results are grouped by file with rank scores:

```
  src/indexer/config.py [rank: 0.1373]
    5:from dataclasses import dataclass, field
    60:class Config:
    ...

  src/indexer/cli.py [rank: 0.1592]
    10:from indexer.config import Config
    ...
```

### 5. Incremental Updates

Files are tracked by SHA-256 content hash. Running `indexer update` only re-parses files that actually changed. The SQLite database uses `ON DELETE CASCADE` so re-indexing a file automatically cleans up its stale symbols, references, and skeleton.

## Claude Code Integration

Indexer ships with three [Claude Code skills](https://code.claude.com/docs/en/skills) and a PreToolUse hook that can be installed globally.

### Install the skills

```bash
# Install/upgrade CLI + skills together
./install.sh

# Or copy skills manually
cp -r /path/to/indexer/.claude/skills/index-codebase ~/.claude/skills/
cp -r /path/to/indexer/.claude/skills/setup-indexer ~/.claude/skills/
cp -r /path/to/indexer/.claude/skills/explore-with-indexer ~/.claude/skills/
```

### `/index-codebase`

Builds or incrementally updates the structural code index for the current project. Run this at the start of a coding session to ensure the index is fresh.

### `/setup-indexer`

Configures a project for indexer-first navigation:
- Appends comprehensive indexer instructions to `CLAUDE.md` (default workflow, exceptions table, anti-patterns, agent prompt block)
- Installs a PreToolUse hook that reminds agents to use indexer when they reach for `grep`/`glob` with symbol-like patterns
- Ensures `.indexer/` is in `.gitignore`

Run this once per project.

### `/explore-with-indexer`

Spawns an exploration agent pre-loaded with indexer instructions. Use it to investigate unfamiliar code:

```
/explore-with-indexer How does the PageRank computation work?
/explore-with-indexer Trace all callers of Database.connect
```

The agent starts by running `indexer map` to orient itself, then uses indexer commands exclusively for navigation.

### PreToolUse hook

The hook (installed by `/setup-indexer`) watches for Grep and Glob tool calls that look like symbol navigation:

- **Grep with symbol-like patterns** (CamelCase, snake_case, PascalCase, ALL_CAPS) — injects a reminder to use `indexer search`/`refs`/`callers`
- **Glob with broad code patterns** (`**/*.py`, `**/*`) — reminds to use `indexer map`/`find`/`tree`

The hook never blocks — it only adds context to nudge agents toward the index.

### Recommended workflow

```
# In any project, one-time setup:
/setup-indexer
/index-codebase

# Start of each session:
/index-codebase
```

After setup, Claude will automatically use `indexer search`, `indexer map`, `indexer skeleton`, `indexer grep`, etc. instead of grep/glob when navigating the codebase.

## Benchmarking

The benchmark measures real-world agent performance by giving a Claude agent concrete code navigation tasks and running each one twice — once with indexer commands available, once with only traditional tools (grep, find, cat). It compares total API tokens consumed, tool calls, speed, and answer correctness across both modes.

Unlike output-size comparisons, this captures what actually matters: multi-turn token accumulation, agent backtracking, and whether the agent reaches the right answer.

### Run the benchmark

```bash
# Preview auto-generated tasks without calling the API (free)
uv run --extra bench python benchmark.py /path/to/project --dry-run

# Full benchmark (requires ANTHROPIC_API_KEY)
ANTHROPIC_API_KEY=sk-ant-... uv run --extra bench python benchmark.py /path/to/project

# Use a specific model (default: haiku for cost efficiency)
uv run --extra bench python benchmark.py /path/to/project --model claude-sonnet-4-20250514

# Run specific task categories only
uv run --extra bench python benchmark.py /path/to/project --tasks symbol_lookup,caller_trace

# Machine-readable output
uv run --extra bench python benchmark.py /path/to/project --json
```

### How it works

1. **Task generation** — The benchmark queries the project's SQLite index directly to build tasks dynamically. It finds the most-referenced symbols (by cross-file reference count), the file with the most symbol definitions (for skeleton vs cat comparison), common filename substrings, and frequently-referenced identifiers for text search. No hardcoded symbol names or file paths — every task is derived from the actual codebase.

2. **Agent execution** — Each task is sent to a Claude agent with a bash tool. In indexer mode, the agent can use all `indexer` commands. In baseline mode, `indexer` commands are blocked and the agent can only use grep, find, cat, head, tail, and ls. The agent runs until it provides a final answer or hits 15 turns.

3. **Correctness checking** — Ground truth comes from the index (search results, caller lists, symbol names, file paths). The agent's answer is checked for the presence of expected file paths and symbol names, matching on both full paths and filenames. Tasks with many valid results (text search, file discovery) only require one match; focused tasks (symbol lookup, callers) require a majority.

### What it measures

| Metric | What it captures |
|---|---|
| **Input tokens** | Cumulative prompt tokens across all turns (includes growing conversation context) |
| **Output tokens** | Cumulative completion tokens across all turns |
| **Tool calls** | Number of bash invocations the agent needed |
| **Turns** | Conversation round-trips to reach an answer |
| **Correctness** | Whether the answer contains ground truth file paths / symbol names |
| **Wall time** | End-to-end elapsed time per task |
| **Speed improvement** | Percentage faster across all tasks combined |

### Task types

| Category | What it tests | Ground truth source |
|---|---|---|
| `symbol_lookup` | Find where a heavily-referenced symbol is defined | `indexer search` via refs table |
| `caller_trace` | List files that call a symbol with multiple callers | `indexer callers` via refs table |
| `file_understanding` | List functions/classes in a large file (100+ lines) | `indexer skeleton` via symbols table |
| `text_search` | Find files containing a frequently-referenced identifier | `indexer grep` via refs table |
| `file_discovery` | Find files matching a common filename pattern | `indexer find` via files table |

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
  cli.py              CLI entry point (Click) — all commands
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
