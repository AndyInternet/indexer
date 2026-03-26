"""Shared fixtures for indexer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from indexer.config import Config
from indexer.db import Database, FileRecord, RefRecord, SymbolRecord


# ---------- Sample source code strings ----------

SAMPLE_PYTHON = '''\
import os
from pathlib import Path

class Greeter:
    """A simple greeter."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"Hello, {self.name}!"

def helper(x: int) -> int:
    return x + 1

MAX_RETRIES: int = 3
'''

SAMPLE_JAVASCRIPT = """\
import { readFile } from 'fs';

class Parser {
    constructor(options) {
        this.options = options;
    }

    parse(input) {
        return input.split('\\n');
    }
}

function validate(data) {
    return data != null;
}
"""

SAMPLE_GO = """\
package main

import "fmt"

type Server struct {
\tHost string
\tPort int
}

func NewServer(host string, port int) *Server {
\treturn &Server{Host: host, Port: port}
}

func (s *Server) Start() error {
\tfmt.Printf("Starting %s:%d\\n", s.Host, s.Port)
\treturn nil
}
"""

SAMPLE_TYPESCRIPT = """\
import { Request, Response } from 'express';

interface Config {
    port: number;
    host: string;
}

type Handler = (req: Request, res: Response) => void;

class App {
    private config: Config;

    constructor(config: Config) {
        this.config = config;
    }

    listen(): void {
        console.log(`Listening on ${this.config.port}`);
    }
}

function createApp(config: Config): App {
    return new App(config);
}
"""


# ---------- Helpers ----------


def make_tree(root: Path, files: dict[str, str]) -> None:
    """Create files at given relative paths with given content."""
    for rel_path, content in files.items():
        full = root / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)


# ---------- Fixtures ----------


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temp directory with sample source files for multiple languages."""
    make_tree(
        tmp_path,
        {
            "main.py": SAMPLE_PYTHON,
            "lib/parser.js": SAMPLE_JAVASCRIPT,
            "cmd/server.go": SAMPLE_GO,
            "src/app.ts": SAMPLE_TYPESCRIPT,
            "README.md": "# Test Project\n",
            "Makefile": "all:\n\techo hello\n",
        },
    )
    return tmp_path


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """A fresh Database instance with schema initialized."""
    db_path = tmp_path / ".indexer" / "index.db"
    d = Database(db_path)
    d.init_schema()
    yield d
    d.close()


@pytest.fixture
def populated_db(db: Database) -> Database:
    """A Database pre-populated with files, symbols, refs, skeletons."""
    fid1 = db.upsert_file(
        FileRecord(
            id=None,
            path="main.py",
            content_hash="aaa",
            last_modified=1000.0,
            language="python",
            line_count=20,
            byte_size=500,
        )
    )
    fid2 = db.upsert_file(
        FileRecord(
            id=None,
            path="lib/utils.py",
            content_hash="bbb",
            last_modified=1000.0,
            language="python",
            line_count=30,
            byte_size=800,
        )
    )
    db.upsert_file(
        FileRecord(
            id=None,
            path="README.md",
            content_hash="ccc",
            last_modified=1000.0,
            language=None,
            line_count=5,
            byte_size=100,
        )
    )
    db.connect().commit()

    db.insert_symbols(
        [
            SymbolRecord(
                id=None,
                name="Greeter",
                kind="class",
                file_id=fid1,
                line_start=4,
                line_end=12,
                col_start=0,
                col_end=0,
                signature="class Greeter",
                parent_symbol_id=None,
            ),
            SymbolRecord(
                id=None,
                name="greet",
                kind="function",
                file_id=fid1,
                line_start=10,
                line_end=12,
                col_start=4,
                col_end=0,
                signature="def greet(self) -> str",
                parent_symbol_id=None,
            ),
            SymbolRecord(
                id=None,
                name="helper",
                kind="function",
                file_id=fid2,
                line_start=1,
                line_end=5,
                col_start=0,
                col_end=0,
                signature="def helper(x: int) -> int",
                parent_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    # Resolve parent: greet -> Greeter
    db.resolve_parent_symbols(fid1, {"greet": "Greeter"})
    db.connect().commit()

    # main.py references helper from utils.py
    db.insert_refs(
        [
            RefRecord(
                id=None,
                from_file_id=fid1,
                to_symbol_name="helper",
                line=15,
                resolved_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    db.upsert_skeleton(fid1, "class Greeter:\n  def greet(self) -> str:\n    ...", 15)
    db.upsert_skeleton(fid2, "def helper(x: int) -> int:\n  ...", 10)
    db.connect().commit()

    return db


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """A Config instance pointing to tmp_path with default patterns."""
    return Config(root=tmp_path, ignore=[".git", ".indexer", "__pycache__"])
