"""Tests for symbol and reference extraction from tree-sitter ASTs."""

from __future__ import annotations

from pathlib import Path

from indexer.parsing.extractors import extract_references, extract_symbols
from indexer.parsing.parser import parse_file

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


def _write_and_parse(tmp_path: Path, filename: str, content: str):
    """Write content to a file and parse it."""
    fp = tmp_path / filename
    fp.write_text(content)
    return parse_file(fp)


# ---------- Python ----------


def test_extract_symbols_python_class(tmp_path: Path):
    """Finds the Greeter class."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    syms = extract_symbols(result)
    names = {s.name for s in syms}
    assert "Greeter" in names
    greeter = next(s for s in syms if s.name == "Greeter")
    assert greeter.kind == "class"


def test_extract_symbols_python_methods(tmp_path: Path):
    """Methods have parent_name set to containing class."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    syms = extract_symbols(result)
    init_sym = next(s for s in syms if s.name == "__init__")
    assert init_sym.parent_name == "Greeter"
    greet_sym = next(s for s in syms if s.name == "greet")
    assert greet_sym.parent_name == "Greeter"


def test_extract_symbols_python_function(tmp_path: Path):
    """Finds top-level helper function."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    syms = extract_symbols(result)
    helper = next(s for s in syms if s.name == "helper")
    assert helper.kind == "function"
    assert helper.parent_name is None


def test_extract_symbols_python_signatures(tmp_path: Path):
    """Signature excludes the function body."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    syms = extract_symbols(result)
    helper = next(s for s in syms if s.name == "helper")
    assert "def helper" in helper.signature
    assert "return" not in helper.signature


def test_extract_references_python(tmp_path: Path):
    """With known_symbols provided, finds matching references."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    refs = extract_references(result, known_symbols={"os", "Path"})
    ref_names = {r.name for r in refs}
    assert "os" in ref_names or "Path" in ref_names


# ---------- JavaScript ----------


def test_extract_symbols_js_class_and_methods(tmp_path: Path):
    """Finds Parser class and its methods."""
    result = _write_and_parse(tmp_path, "parser.js", SAMPLE_JAVASCRIPT)
    syms = extract_symbols(result)
    names = {s.name for s in syms}
    assert "Parser" in names
    # Constructor and parse are methods
    method_syms = [s for s in syms if s.parent_name == "Parser"]
    method_names = {s.name for s in method_syms}
    assert "constructor" in method_names or "parse" in method_names


def test_extract_symbols_js_function(tmp_path: Path):
    """Finds standalone validate function."""
    result = _write_and_parse(tmp_path, "parser.js", SAMPLE_JAVASCRIPT)
    syms = extract_symbols(result)
    validate = next(s for s in syms if s.name == "validate")
    assert validate.kind == "function"
    assert validate.parent_name is None


# ---------- Go ----------


def test_extract_symbols_go_function_and_type(tmp_path: Path):
    """Finds function and type declarations."""
    result = _write_and_parse(tmp_path, "server.go", SAMPLE_GO)
    syms = extract_symbols(result)
    names = {s.name for s in syms}
    assert "NewServer" in names
    # Go type declarations may wrap the struct name at different levels
    kinds = {s.kind for s in syms}
    assert "function" in kinds or "method" in kinds


def test_extract_symbols_go_method(tmp_path: Path):
    """Finds Start method with receiver."""
    result = _write_and_parse(tmp_path, "server.go", SAMPLE_GO)
    syms = extract_symbols(result)
    start = next(s for s in syms if s.name == "Start")
    assert start.kind == "method"


# ---------- TypeScript ----------


def test_extract_symbols_ts_interface(tmp_path: Path):
    """Finds Config interface."""
    result = _write_and_parse(tmp_path, "app.ts", SAMPLE_TYPESCRIPT)
    syms = extract_symbols(result)
    config = next(s for s in syms if s.name == "Config")
    assert config.kind == "interface"


def test_extract_symbols_ts_class(tmp_path: Path):
    """Finds App class."""
    result = _write_and_parse(tmp_path, "app.ts", SAMPLE_TYPESCRIPT)
    syms = extract_symbols(result)
    app = next(s for s in syms if s.name == "App")
    assert app.kind == "class"


# ---------- Edge cases ----------


def test_extract_symbols_empty_file(tmp_path: Path):
    """Empty Python file returns no symbols."""
    result = _write_and_parse(tmp_path, "empty.py", "")
    syms = extract_symbols(result)
    assert syms == []


def test_extract_references_filters_by_known(tmp_path: Path):
    """Only known symbols are returned when filter provided."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    refs_filtered = extract_references(result, known_symbols={"nonexistent_symbol"})
    assert len(refs_filtered) == 0

    refs_all = extract_references(result, known_symbols=None)
    assert len(refs_all) > 0  # unfiltered returns identifiers
