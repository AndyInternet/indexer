# Indexer

AI-optimized codebase index generator. Uses Tree-sitter AST parsing, code skeleton extraction, and PageRank-based repo mapping to give AI coding agents surgical precision when navigating code — reducing token consumption by up to 90%.

Built from research on [advanced codebase indexing strategies for AI agents](research.md).

## Quickstart

### Install the CLI

```bash
uv tool install /path/to/indexer
```

Once installed, `indexer` is available as a command anywhere on your system. To upgrade, run the same command with `--force`.

### Index a codebase

The index is built automatically on first query — just start using any command. To explicitly build or rebuild:

```bash
cd /path/to/your/project
indexer init .          # Full index from scratch
indexer update .        # Incremental update (changed files only)
```

The index is stored in `.indexer/index.db`. It auto-updates on subsequent queries when it detects changes (git state or file mtimes).

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
```

> **Note:** You don't need to run `indexer update` manually — query commands auto-detect changes and update the index before returning results.

## Claude Code Integration

The plugin gives Claude Code auto-allowed permissions and a PreToolUse hook that enforces `indexer` usage — all configured by a single command.

### Install the plugin

```bash
cd /path/to/your/project
indexer plugin install
```

This writes `.claude/settings.json` in the project with:

- Auto-allowed permissions for all `indexer` commands
- PreToolUse hook that intercepts Grep/Glob/Bash/LSP and redirects to `indexer`

Start a new Claude Code session to activate.

### Manage the plugin

```bash
indexer plugin status      # Check if installed
indexer plugin uninstall   # Remove from project
```

### PreToolUse hook

The hook intercepts Grep, Glob, and Bash tool calls and redirects them to the appropriate `indexer` command:

- **Grep with symbol-like patterns** (camelCase, snake_case, PascalCase, SCREAMING_SNAKE, $-prefixed) → `indexer search`/`refs`/`callers`
- **Grep with any other pattern** → `indexer grep` (PageRank-ranked results)
- **Glob** (all patterns) → `indexer find`/`map`/`tree`
- **Bash `find`** → `indexer find`
- **Bash `grep`/`rg`** → `indexer grep`
- **Bash `ls -R`** → `indexer tree`
- **Bash `cat` on source files** → `indexer skeleton`/`impl`

The hook denies the tool call and provides the correct `indexer` alternative in the denial reason. Non-code commands (`git`, `npm`, `pytest`, `indexer` itself, etc.) pass through unblocked.

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
- **Self-healing** — The index auto-builds on first query and auto-updates when it detects changes. In git repos, a fingerprint of `HEAD + git status` catches branch switches, new commits, and uncommitted edits. In non-git repos, file mtimes are fingerprinted instead. No manual `init` or `update` needed.

## What It Indexes

Indexer generates a local SQLite index of your codebase containing:

- **Code skeletons** — imports + function signatures + class structure, no bodies (~10% of original tokens)
- **PageRank repo map** — dependency-graph-ranked overview of the most important files, fitted to a configurable token budget
- **Symbol index** — searchable database of all definitions and cross-file references
- **Full-text search** — PageRank-ranked grep across all indexed files, so the most important results come first
- **File discovery** — find files by pattern and view directory trees from the index, no filesystem walk needed
- **Incremental updates** — SHA-256 hashing means only changed files are re-parsed
- **Auto-freshness** — index auto-builds on first query and auto-updates when git state or file mtimes change

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
| `indexer config show` | Print current config as JSON. |
| `indexer config reset` | Reset config to seed defaults. |
| `indexer config ignore <pattern>` | Add a pattern to the ignore list. |
| `indexer config allow <pattern>` | Add a pattern to the allow list (overrides ignore). |
| `indexer config remove <pattern>` | Remove a pattern from the ignore or allow list. |
| `indexer plugin install` | Install the Claude Code plugin into the current project. |
| `indexer plugin uninstall` | Remove the Claude Code plugin from the current project. |
| `indexer plugin status` | Check if the Claude Code plugin is installed. |

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

### 5. Auto-Freshness and Incremental Updates

Every query command checks a stored fingerprint before running. In git repos, the fingerprint is `sha256(HEAD commit + git status --porcelain)`, which captures branch switches, new commits, staged changes, unstaged edits, and untracked files — all in one ~10ms check. In non-git repos, file mtimes are fingerprinted instead. If the fingerprint changed, an incremental update runs automatically before the query returns results.

Files are tracked by SHA-256 content hash, so only changed files are re-parsed. The SQLite database uses `ON DELETE CASCADE` so re-indexing a file automatically cleans up its stale symbols, references, and skeleton.

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

All indexer configuration lives in `.indexer/config.json`, created automatically on first use with sensible defaults. The file has two keys:

- **`ignore`** — patterns to exclude from the index (gitignore syntax)
- **`allow`** — patterns that override `ignore`, re-including specific paths

```json
{
  "ignore": [
    ".git", ".indexer", "__pycache__", "node_modules", "vendor",
    ".venv", "venv", ".env", "dist", "build", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "*.pyc", "*.pyo", "*.so", "*.dylib", "*.dll", "*.exe",
    "*.o", "*.a", "*.class", "*.jar", "*.wasm",
    "*.min.js", "*.min.css", "*.map",
    "*.lock", "package-lock.json", "yarn.lock",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.svg",
    "*.woff", "*.woff2", "*.ttf", "*.eot",
    "*.pdf", "*.zip", "*.tar.gz", "*.tgz"
  ],
  "allow": []
}
```

The `.gitignore` in your project root is also respected (merged with `ignore` at scan time). `.git/` and `.indexer/` are always excluded regardless of config.

The `.indexer/` directory includes its own `.gitignore` (containing `*`) so it self-ignores even if the project doesn't explicitly exclude it.

### Ignoring additional paths

Edit `.indexer/config.json` directly or use the CLI:

```bash
# Ignore a directory
indexer config ignore "generated"

# Ignore files by extension
indexer config ignore "*.pb.go"

# Re-index to apply
indexer init .
```

### Allowing paths inside ignored directories

The `allow` list re-includes specific paths that would otherwise be excluded by `ignore`. This is useful when you need to index a subdirectory inside an otherwise-ignored directory.

For example, to index a specific library inside `vendor/` while keeping the rest of `vendor/` ignored:

```bash
# Allow one subdirectory inside vendor
indexer config allow "vendor/my-special-lib/**"

# Re-index to apply
indexer init .
```

This works by descending into `vendor/` only far enough to reach `my-special-lib/`, without scanning the rest of `vendor/`. The equivalent manual edit to `.indexer/config.json`:

```json
{
  "ignore": ["vendor", "..."],
  "allow": ["vendor/my-special-lib/**"]
}
```

More examples:

```bash
# Allow a scoped npm package inside node_modules
indexer config allow "node_modules/@myorg/shared-types/**"

# Allow only Go files inside vendor
indexer config allow "vendor/**/*.go"

# Allow a specific file
indexer config allow "vendor/important.go"
```

### Removing patterns

```bash
# Stop ignoring a pattern
indexer config remove "*.lock"

# Stop allowing a pattern
indexer config remove "vendor/my-special-lib/**"

# Re-index to apply
indexer init .
```

### Precedence rules

1. A file is **included** by default
2. If it matches any `ignore` pattern or `.gitignore` entry, it is **excluded**
3. If it matches any `allow` pattern, it is **re-included** (allow overrides ignore)
4. `.git/` and `.indexer/` are **always excluded**

### Viewing and resetting config

```bash
# Print current config
indexer config show

# Reset to defaults
indexer config reset
```

Config changes are detected automatically — the index fingerprint includes the config file, so query commands will trigger a re-index when the config changes.

## Architecture

```
src/indexer/
  cli.py              CLI entry point (Click) — all commands
  db.py               SQLite schema + CRUD (WAL mode, cascade deletes)
  freshness.py         Auto-freshness via git/mtime fingerprinting
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
