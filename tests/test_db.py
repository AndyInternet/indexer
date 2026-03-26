"""Tests for the SQLite database layer."""

from __future__ import annotations

import pytest

from indexer.db import Database, FileRecord, RefRecord, SymbolRecord


# ---------- File CRUD ----------


def test_upsert_file_insert(db: Database):
    """Inserting a new file returns an integer ID."""
    fid = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="abc",
            last_modified=1.0,
            language="python",
            line_count=10,
            byte_size=100,
        )
    )
    db.connect().commit()
    assert isinstance(fid, int)
    assert fid > 0


def test_upsert_file_update(db: Database):
    """Upserting same path with different hash updates in-place."""
    fid1 = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="abc",
            last_modified=1.0,
            language="python",
            line_count=10,
            byte_size=100,
        )
    )
    db.connect().commit()
    fid2 = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="def",
            last_modified=2.0,
            language="python",
            line_count=20,
            byte_size=200,
        )
    )
    db.connect().commit()
    assert fid1 == fid2
    rec = db.get_file("a.py")
    assert rec.content_hash == "def"
    assert rec.line_count == 20


def test_get_file_by_path(db: Database):
    """get_file returns correct FileRecord."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="b.py",
            content_hash="xyz",
            last_modified=5.0,
            language="python",
            line_count=15,
            byte_size=300,
        )
    )
    db.connect().commit()
    rec = db.get_file("b.py")
    assert rec is not None
    assert rec.path == "b.py"
    assert rec.content_hash == "xyz"


def test_get_file_not_found(db: Database):
    """get_file returns None for missing path."""
    assert db.get_file("nonexistent.py") is None


def test_get_file_by_id(db: Database):
    """get_file_by_id returns correct record."""
    fid = db.upsert_file(
        FileRecord(
            id=None,
            path="c.py",
            content_hash="111",
            last_modified=1.0,
            language="python",
            line_count=5,
            byte_size=50,
        )
    )
    db.connect().commit()
    rec = db.get_file_by_id(fid)
    assert rec is not None
    assert rec.path == "c.py"


def test_get_all_files(db: Database):
    """get_all_files returns all inserted files."""
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
    files = db.get_all_files()
    assert len(files) == 2
    assert {f.path for f in files} == {"a.py", "b.py"}


def test_delete_file(db: Database):
    """delete_file removes the record."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="del.py",
            content_hash="x",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()
    db.delete_file("del.py")
    db.connect().commit()
    assert db.get_file("del.py") is None


def test_get_all_file_hashes(db: Database):
    """get_all_file_hashes returns {path: hash} dict."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="aaa",
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
            content_hash="bbb",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()
    hashes = db.get_all_file_hashes()
    assert hashes == {"a.py": "aaa", "b.py": "bbb"}


def test_get_all_file_paths(db: Database):
    """get_all_file_paths returns sorted list."""
    db.upsert_file(
        FileRecord(
            id=None,
            path="z.py",
            content_hash="z",
            last_modified=1.0,
            language="python",
            line_count=1,
            byte_size=1,
        )
    )
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
    db.connect().commit()
    paths = db.get_all_file_paths()
    assert paths == ["a.py", "z.py"]


# ---------- Symbol CRUD ----------


def test_insert_and_get_symbols(db: Database):
    """insert_symbols + get_symbols_by_file roundtrip."""
    fid = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="a",
            last_modified=1.0,
            language="python",
            line_count=10,
            byte_size=100,
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
    syms = db.get_symbols_by_file(fid)
    assert len(syms) == 1
    assert syms[0].name == "foo"
    assert syms[0].kind == "function"


def test_search_symbols_like(populated_db: Database):
    """search_symbols with LIKE pattern finds partial matches."""
    results = populated_db.search_symbols("greet")
    names = {r[0].name for r in results}
    assert "Greeter" in names
    assert "greet" in names


def test_search_symbols_no_match(populated_db: Database):
    """search_symbols returns empty for non-existent name."""
    assert populated_db.search_symbols("zzzznonexistent") == []


def test_get_symbol_by_name(populated_db: Database):
    """get_symbol_by_name returns exact match with file path."""
    results = populated_db.get_symbol_by_name("helper")
    assert len(results) == 1
    sym, path = results[0]
    assert sym.name == "helper"
    assert path == "lib/utils.py"


def test_get_all_symbol_names(populated_db: Database):
    """get_all_symbol_names returns set of distinct names."""
    names = populated_db.get_all_symbol_names()
    assert names == {"Greeter", "greet", "helper"}


def test_get_all_symbol_names_by_lang(db: Database):
    """get_all_symbol_names filtered by language."""
    fid_py = db.upsert_file(
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
    fid_js = db.upsert_file(
        FileRecord(
            id=None,
            path="b.js",
            content_hash="b",
            last_modified=1.0,
            language="javascript",
            line_count=1,
            byte_size=1,
        )
    )
    db.connect().commit()
    db.insert_symbols(
        [
            SymbolRecord(
                id=None,
                name="py_func",
                kind="function",
                file_id=fid_py,
                line_start=1,
                line_end=1,
                col_start=0,
                col_end=0,
                signature="def py_func()",
                parent_symbol_id=None,
            ),
            SymbolRecord(
                id=None,
                name="js_func",
                kind="function",
                file_id=fid_js,
                line_start=1,
                line_end=1,
                col_start=0,
                col_end=0,
                signature="function js_func()",
                parent_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()
    py_names = db.get_all_symbol_names(language="python")
    assert py_names == {"py_func"}
    js_names = db.get_all_symbol_names(language="javascript")
    assert js_names == {"js_func"}


# ---------- Reference CRUD ----------


def test_insert_and_get_refs(db: Database):
    """insert_refs + get_all_refs roundtrip."""
    fid = db.upsert_file(
        FileRecord(
            id=None,
            path="a.py",
            content_hash="a",
            last_modified=1.0,
            language="python",
            line_count=10,
            byte_size=100,
        )
    )
    db.connect().commit()
    db.insert_refs(
        [
            RefRecord(
                id=None,
                from_file_id=fid,
                to_symbol_name="foo",
                line=5,
                resolved_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()
    refs = db.get_all_refs()
    assert len(refs) == 1
    assert refs[0].to_symbol_name == "foo"


def test_get_refs_to_symbol(populated_db: Database):
    """get_refs_to_symbol returns (RefRecord, file_path) tuples."""
    results = populated_db.get_refs_to_symbol("helper")
    assert len(results) == 1
    ref, path = results[0]
    assert ref.to_symbol_name == "helper"
    assert path == "main.py"


def test_delete_refs_for_file(db: Database):
    """delete_refs_for_file clears refs for one file."""
    fid1 = db.upsert_file(
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
    fid2 = db.upsert_file(
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
    db.insert_refs(
        [
            RefRecord(
                id=None,
                from_file_id=fid1,
                to_symbol_name="x",
                line=1,
                resolved_symbol_id=None,
            ),
            RefRecord(
                id=None,
                from_file_id=fid2,
                to_symbol_name="y",
                line=1,
                resolved_symbol_id=None,
            ),
        ]
    )
    db.connect().commit()
    db.delete_refs_for_file(fid1)
    db.connect().commit()
    refs = db.get_all_refs()
    assert len(refs) == 1
    assert refs[0].to_symbol_name == "y"


# ---------- Parent resolution ----------


def test_resolve_parent_symbols(populated_db: Database):
    """resolve_parent_symbols sets parent_symbol_id correctly."""
    frec = populated_db.get_file("main.py")
    syms = populated_db.get_symbols_by_file(frec.id)
    greet_sym = next(s for s in syms if s.name == "greet")
    greeter_sym = next(s for s in syms if s.name == "Greeter")
    assert greet_sym.parent_symbol_id == greeter_sym.id


def test_resolve_parent_symbols_empty(db: Database):
    """Empty parent_map is a no-op."""
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
    db.resolve_parent_symbols(fid, {})  # should not raise


# ---------- Skeletons ----------


def test_upsert_and_get_skeleton(db: Database):
    """Skeleton insert and retrieve roundtrip."""
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
    db.upsert_skeleton(fid, "def foo():\n  ...", 5)
    db.connect().commit()
    assert db.get_skeleton(fid) == "def foo():\n  ..."


def test_upsert_skeleton_update(db: Database):
    """Upserting skeleton overwrites existing."""
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
    db.upsert_skeleton(fid, "old", 3)
    db.connect().commit()
    db.upsert_skeleton(fid, "new", 3)
    db.connect().commit()
    assert db.get_skeleton(fid) == "new"


def test_get_skeleton_missing(db: Database):
    """get_skeleton returns None for file without skeleton."""
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
    assert db.get_skeleton(fid) is None


# ---------- Metadata ----------


def test_set_get_metadata(db: Database):
    """Metadata key-value roundtrip."""
    db.set_metadata("version", "1.0")
    assert db.get_metadata("version") == "1.0"


def test_set_metadata_upsert(db: Database):
    """Setting same key overwrites."""
    db.set_metadata("key", "old")
    db.set_metadata("key", "new")
    assert db.get_metadata("key") == "new"


# ---------- CASCADE + transaction ----------


def test_cascade_delete_file(populated_db: Database):
    """Deleting a file cascades to symbols, refs, and skeletons."""
    frec = populated_db.get_file("main.py")
    fid = frec.id

    # Verify data exists before delete
    assert len(populated_db.get_symbols_by_file(fid)) > 0
    assert populated_db.get_skeleton(fid) is not None

    populated_db.delete_file("main.py")
    populated_db.connect().commit()

    assert populated_db.get_symbols_by_file(fid) == []
    assert populated_db.get_skeleton(fid) is None
    # Refs from this file should also be gone
    assert populated_db.get_all_refs() == []


def test_transaction_rollback(db: Database):
    """Transaction rolls back on exception."""
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
    db.connect().commit()

    with pytest.raises(ValueError):
        with db.transaction():
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
            raise ValueError("test rollback")

    # b.py should not exist after rollback
    assert db.get_file("b.py") is None


# ---------- Stats ----------


def test_get_stats(populated_db: Database):
    """get_stats returns counts for all 4 tables."""
    stats = populated_db.get_stats()
    assert stats["files"] == 3
    assert stats["symbols"] == 3
    assert stats["refs"] == 1
    assert stats["skeletons"] == 2
