"""Tests for skeleton extraction."""

from __future__ import annotations

from pathlib import Path

from indexer.parsing.parser import parse_file
from indexer.skeleton.extractor import extract_skeleton

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


def _write_and_parse(tmp_path: Path, filename: str, content: str):
    fp = tmp_path / filename
    fp.write_text(content)
    return parse_file(fp)


def test_skeleton_python_elides_bodies(tmp_path: Path):
    """Function bodies are replaced with '...'."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    skel = extract_skeleton(result)
    assert "..." in skel
    # The actual return statement should not appear
    assert 'return f"Hello' not in skel
    assert "return x + 1" not in skel


def test_skeleton_python_keeps_imports(tmp_path: Path):
    """Import statements appear verbatim."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    skel = extract_skeleton(result)
    assert "import os" in skel
    assert "from pathlib import Path" in skel


def test_skeleton_python_class_structure(tmp_path: Path):
    """Class header and method signatures are preserved."""
    result = _write_and_parse(tmp_path, "main.py", SAMPLE_PYTHON)
    skel = extract_skeleton(result)
    assert "class Greeter" in skel
    assert "def greet(self)" in skel
    assert "def __init__" in skel


def test_skeleton_js_elides_bodies(tmp_path: Path):
    """JS function bodies are replaced with '{ ... }'."""
    result = _write_and_parse(tmp_path, "parser.js", SAMPLE_JAVASCRIPT)
    skel = extract_skeleton(result)
    assert "{ ... }" in skel
    assert "return input.split" not in skel


def test_skeleton_go_elides_bodies(tmp_path: Path):
    """Go function bodies are replaced with '{ ... }'."""
    result = _write_and_parse(tmp_path, "server.go", SAMPLE_GO)
    skel = extract_skeleton(result)
    assert "{ ... }" in skel
    assert "fmt.Printf" not in skel


def test_skeleton_empty_file(tmp_path: Path):
    """Empty file produces empty or whitespace-only skeleton."""
    result = _write_and_parse(tmp_path, "empty.py", "")
    skel = extract_skeleton(result)
    assert skel.strip() == ""
