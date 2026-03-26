"""Tests for dependency graph construction."""

from __future__ import annotations

from indexer.db import Database, FileRecord, RefRecord, SymbolRecord
from indexer.graph.builder import build_dependency_graph


def test_empty_db(db: Database):
    """No files produces an empty graph."""
    G = build_dependency_graph(db)
    assert len(G.nodes) == 0
    assert len(G.edges) == 0


def test_files_no_refs(db: Database):
    """Files become nodes but no edges without references."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="a",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.upsert_file(
        FileRecord(
            id=None,
            path="b.py",
            content_hash="b",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()
    G = build_dependency_graph(db)
    assert len(G.nodes) == 2
    assert len(G.edges) == 0


def test_cross_file_ref(db: Database):
    """Reference from A to symbol in B creates edge A -> B."""
    fid_a = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="a",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    fid_b = db.upsert_file(
        FileRecord(
            id=None,
            path="b.py",
            content_hash="b",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()

    db.insert_symbols(
        [
            SymbolRecord(
                id=None,
                name="foo",
                kind="function",
                file_id=fid_b,
                line_start=1,
                line_end=3,
                col_start=0,
                col_end=0,
                signature="def foo()",
                parent_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    db.insert_refs(
        [
            RefRecord(
                id=None,
                from_file_id=fid_a,
                to_symbol_name="foo",
                line=5,
                resolved_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    G = build_dependency_graph(db)
    assert G.has_edge("a.py", "b.py")
    assert not G.has_edge("b.py", "a.py")


def test_self_ref_excluded(db: Database):
    """Reference to symbol in the same file creates no edge."""
    fid = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="a",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()

    db.insert_symbols(
        [
            SymbolRecord(
                id=None,
                name="foo",
                kind="function",
                file_id=fid,
                line_start=1,
                line_end=3,
                col_start=0,
                col_end=0,
                signature="def foo()",
                parent_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    db.insert_refs(
        [
            RefRecord(
                id=None,
                from_file_id=fid,
                to_symbol_name="foo",
                line=10,
                resolved_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()

    G = build_dependency_graph(db)
    assert len(G.edges) == 0
