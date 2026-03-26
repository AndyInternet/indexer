"""Tests for repo map rendering."""

from __future__ import annotations

from indexer.db import Database, FileRecord
from indexer.graph.repomap import render_repo_map


def test_empty_scores(db: Database):
    """Empty scores returns the empty index message."""
    output = render_repo_map(db, {})
    assert "Empty index" in output


def test_single_file_with_symbols(populated_db: Database):
    """Renders file path and symbol signatures."""
    output = render_repo_map(populated_db, {"main.py": 1.0}, token_budget=4096)
    assert "main.py" in output
    assert "Greeter" in output


def test_class_methods_nested(populated_db: Database):
    """Methods are rendered nested under their class."""
    output = render_repo_map(populated_db, {"main.py": 1.0}, token_budget=4096)
    assert "class Greeter" in output
    assert "def greet(self)" in output


def test_token_budget_limits(populated_db: Database):
    """Very small budget still produces at least the top file."""
    output = render_repo_map(
        populated_db,
        {"main.py": 1.0, "lib/utils.py": 0.5},
        token_budget=10,
    )
    # Should produce at least something (the minimum is top file)
    assert len(output) > 0
    assert "main.py" in output


def test_file_without_symbols(db: Database):
    """File without symbols renders just the path."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="README.md",
            content_hash="aaa",
            last_modified=1.0,
            language=None,
            line_count=5,
            byte_size=100,
        )
    )
    db.connect().commit()
    output = render_repo_map(db, {"README.md": 1.0}, token_budget=4096)
    assert "README.md" in output
