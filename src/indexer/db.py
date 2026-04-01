"""SQLite database layer for the codebase index."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,
    last_modified REAL NOT NULL,
    language TEXT,
    line_count INTEGER,
    byte_size INTEGER
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    col_start INTEGER,
    col_end INTEGER,
    signature TEXT,
    parent_symbol_id INTEGER REFERENCES symbols(id),
    UNIQUE(file_id, name, kind, line_start)
);

CREATE TABLE IF NOT EXISTS refs (
    id INTEGER PRIMARY KEY,
    from_file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    to_symbol_name TEXT NOT NULL,
    line INTEGER,
    resolved_symbol_id INTEGER REFERENCES symbols(id)
);

CREATE TABLE IF NOT EXISTS skeletons (
    id INTEGER PRIMARY KEY,
    file_id INTEGER UNIQUE NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    skeleton_text TEXT NOT NULL,
    token_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind);
CREATE INDEX IF NOT EXISTS idx_refs_from ON refs(from_file_id);
CREATE INDEX IF NOT EXISTS idx_refs_to ON refs(to_symbol_name);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class FileRecord:
    id: int | None
    path: str
    content_hash: str
    last_modified: float
    language: str | None
    line_count: int | None
    byte_size: int | None


@dataclass
class SymbolRecord:
    id: int | None
    name: str
    kind: str
    file_id: int
    line_start: int
    line_end: int
    col_start: int | None
    col_end: int | None
    signature: str | None
    parent_symbol_id: int | None


@dataclass
class RefRecord:
    id: int | None
    from_file_id: int
    to_symbol_name: str
    line: int | None
    resolved_symbol_id: int | None


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            gitignore = self.db_path.parent / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text("*\n")
            self._conn = sqlite3.connect(str(self.db_path), timeout=10)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_schema(self) -> None:
        conn = self.connect()
        conn.executescript(SCHEMA)
        conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # --- Files ---

    def upsert_file(self, f: FileRecord) -> int:
        conn = self.connect()
        conn.execute(
            """INSERT INTO files (path, content_hash, last_modified, language, line_count, byte_size)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                   content_hash=excluded.content_hash,
                   last_modified=excluded.last_modified,
                   language=excluded.language,
                   line_count=excluded.line_count,
                   byte_size=excluded.byte_size""",
            (f.path, f.content_hash, f.last_modified, f.language, f.line_count, f.byte_size),
        )
        # lastrowid is unreliable on ON CONFLICT UPDATE; query the actual id
        row = conn.execute("SELECT id FROM files WHERE path = ?", (f.path,)).fetchone()
        return row["id"]

    def get_file(self, path: str) -> FileRecord | None:
        conn = self.connect()
        row = conn.execute("SELECT * FROM files WHERE path = ?", (path,)).fetchone()
        if row is None:
            return None
        return FileRecord(**dict(row))

    def get_file_by_id(self, file_id: int) -> FileRecord | None:
        conn = self.connect()
        row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
        if row is None:
            return None
        return FileRecord(**dict(row))

    def get_all_files(self) -> list[FileRecord]:
        conn = self.connect()
        rows = conn.execute("SELECT * FROM files").fetchall()
        return [FileRecord(**dict(r)) for r in rows]

    def delete_file(self, path: str) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM files WHERE path = ?", (path,))

    def get_all_file_hashes(self) -> dict[str, str]:
        conn = self.connect()
        rows = conn.execute("SELECT path, content_hash FROM files").fetchall()
        return {r["path"]: r["content_hash"] for r in rows}

    # --- Symbols ---

    def insert_symbols(self, symbols: list[SymbolRecord]) -> None:
        conn = self.connect()
        conn.executemany(
            """INSERT OR REPLACE INTO symbols
               (name, kind, file_id, line_start, line_end, col_start, col_end, signature, parent_symbol_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (s.name, s.kind, s.file_id, s.line_start, s.line_end,
                 s.col_start, s.col_end, s.signature, s.parent_symbol_id)
                for s in symbols
            ],
        )

    def get_symbols_by_file(self, file_id: int) -> list[SymbolRecord]:
        conn = self.connect()
        rows = conn.execute("SELECT * FROM symbols WHERE file_id = ?", (file_id,)).fetchall()
        return [SymbolRecord(**dict(r)) for r in rows]

    def search_symbols(self, query: str) -> list[tuple[SymbolRecord, str]]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT s.*, f.path as file_path FROM symbols s
               JOIN files f ON s.file_id = f.id
               WHERE s.name LIKE ?
               ORDER BY s.name""",
            (f"%{query}%",),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            file_path = d.pop("file_path")
            results.append((SymbolRecord(**d), file_path))
        return results

    def get_symbol_by_name(self, name: str) -> list[tuple[SymbolRecord, str]]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT s.*, f.path as file_path FROM symbols s
               JOIN files f ON s.file_id = f.id
               WHERE s.name = ?""",
            (name,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            file_path = d.pop("file_path")
            results.append((SymbolRecord(**d), file_path))
        return results

    def get_all_symbol_names(self, language: str | None = None) -> set[str]:
        conn = self.connect()
        if language:
            rows = conn.execute(
                "SELECT DISTINCT s.name FROM symbols s "
                "JOIN files f ON s.file_id = f.id "
                "WHERE f.language = ?",
                (language,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT name FROM symbols").fetchall()
        return {r["name"] for r in rows}

    # --- References ---

    def insert_refs(self, refs: list[RefRecord]) -> None:
        conn = self.connect()
        conn.executemany(
            """INSERT INTO refs (from_file_id, to_symbol_name, line, resolved_symbol_id)
               VALUES (?, ?, ?, ?)""",
            [(r.from_file_id, r.to_symbol_name, r.line, r.resolved_symbol_id) for r in refs],
        )

    def get_refs_to_symbol(self, symbol_name: str) -> list[tuple[RefRecord, str]]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT r.*, f.path as file_path FROM refs r
               JOIN files f ON r.from_file_id = f.id
               WHERE r.to_symbol_name = ?
               ORDER BY f.path, r.line""",
            (symbol_name,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            file_path = d.pop("file_path")
            results.append((RefRecord(**d), file_path))
        return results

    def get_all_refs(self) -> list[RefRecord]:
        conn = self.connect()
        rows = conn.execute("SELECT * FROM refs").fetchall()
        return [RefRecord(**dict(r)) for r in rows]

    def delete_refs_for_file(self, file_id: int) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM refs WHERE from_file_id = ?", (file_id,))

    def delete_symbols_for_file(self, file_id: int) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_id,))

    def resolve_parent_symbols(self, file_id: int, parent_map: dict[str, str]) -> None:
        """Set parent_symbol_id for symbols whose parent_name was extracted.

        parent_map: {child_symbol_name: parent_symbol_name}
        """
        if not parent_map:
            return
        conn = self.connect()
        for child_name, parent_name in parent_map.items():
            conn.execute(
                """UPDATE symbols SET parent_symbol_id = (
                       SELECT id FROM symbols
                       WHERE name = ? AND file_id = ? AND kind IN ('class', 'interface')
                       LIMIT 1
                   )
                   WHERE name = ? AND file_id = ?""",
                (parent_name, file_id, child_name, file_id),
            )

    # --- Skeletons ---

    def upsert_skeleton(self, file_id: int, skeleton_text: str, token_count: int) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT INTO skeletons (file_id, skeleton_text, token_count)
               VALUES (?, ?, ?)
               ON CONFLICT(file_id) DO UPDATE SET
                   skeleton_text=excluded.skeleton_text,
                   token_count=excluded.token_count""",
            (file_id, skeleton_text, token_count),
        )

    def get_skeleton(self, file_id: int) -> str | None:
        conn = self.connect()
        row = conn.execute(
            "SELECT skeleton_text FROM skeletons WHERE file_id = ?", (file_id,)
        ).fetchone()
        return row["skeleton_text"] if row else None

    # --- File paths ---

    def get_all_file_paths(self) -> list[str]:
        """Return all indexed file paths, sorted."""
        conn = self.connect()
        rows = conn.execute("SELECT path FROM files ORDER BY path").fetchall()
        return [r["path"] for r in rows]

    # --- Metadata ---

    def get_metadata(self, key: str) -> str | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return row["value"] if row else None

    def set_metadata(self, key: str, value: str) -> None:
        conn = self.connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()

    # --- Stats ---

    def get_stats(self) -> dict[str, int]:
        conn = self.connect()
        stats = {}
        for table in ("files", "symbols", "refs", "skeletons"):
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()  # noqa: S608
            stats[table] = row["cnt"]
        return stats
