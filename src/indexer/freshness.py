"""Staleness detection for the index via filesystem fingerprinting.

Git repos:     fingerprint = sha256(HEAD + git status --porcelain)
Non-git repos: fingerprint = sha256(sorted mtimes of all indexable files)
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import click

from indexer.db import Database


def _git_fingerprint(root: Path) -> str | None:
    """Compute a fingerprint from git state. Returns None if not a git repo."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=root, timeout=5,
        )
        if head.returncode != 0:
            return None

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        if status.returncode != 0:
            return None

        raw = head.stdout.strip() + "\n" + status.stdout
        return hashlib.sha256(raw.encode()).hexdigest()
    except (OSError, subprocess.TimeoutExpired):
        return None


def _fs_fingerprint(root: Path) -> str:
    """Compute a fingerprint from file mtimes for non-git repos."""
    from indexer.config import Config

    config = Config(root=root)

    # Walk the directory using the same ignore patterns as the scanner,
    # but only collect path + mtime — much cheaper than hashing contents.
    import pathspec

    ignore_patterns = config.ignore_patterns
    spec = pathspec.PathSpec.from_lines("gitwildmatch", ignore_patterns)

    entries: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        # Prune ignored directories
        dirnames[:] = [
            d for d in dirnames
            if not spec.match_file(os.path.join(rel_dir, d, ""))
        ]

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            if spec.match_file(rel_path):
                continue
            try:
                mtime = os.path.getmtime(os.path.join(dirpath, fname))
                entries.append(f"{rel_path}:{mtime}")
            except OSError:
                continue

    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def compute_fingerprint(root: Path) -> str:
    """Compute a filesystem fingerprint. Uses git if available, falls back to mtimes."""
    git_fp = _git_fingerprint(root)
    if git_fp is not None:
        return git_fp
    return _fs_fingerprint(root)


def save_freshness(db: Database, root: Path) -> None:
    """Record current fingerprint after indexing."""
    fp = compute_fingerprint(root)
    db.set_metadata("fingerprint", fp)


def check_freshness(db: Database, root: Path) -> str | None:
    """Check if the index is stale. Returns a reason string if stale, None if fresh."""
    stored_fp = db.get_metadata("fingerprint")
    if not stored_fp:
        # Old index without fingerprint — treat as stale
        return "no fingerprint stored"

    current_fp = compute_fingerprint(root)
    if stored_fp != current_fp:
        return "files changed"

    return None


def ensure_fresh(db: Database, root: Path, auto_update: bool = True) -> None:
    """Check freshness and auto-update if stale. Called by query commands."""
    reason = check_freshness(db, root)
    if reason is None:
        return

    if auto_update:
        click.echo(f"Index stale ({reason}), updating...", err=True)
        _run_update(db, root)
    else:
        click.echo(
            f"Warning: index may be stale ({reason}). "
            "Run 'indexer update .' to refresh.",
            err=True,
        )


def _run_update(db: Database, root: Path) -> None:
    """Perform an incremental update inline."""
    from indexer.config import Config
    from indexer.db import FileRecord, RefRecord, SymbolRecord
    from indexer.parsing.extractors import extract_references, extract_symbols
    from indexer.parsing.languages import detect_language
    from indexer.parsing.parser import parse_file
    from indexer.scanner import detect_changes, scan_directory
    from indexer.skeleton.extractor import extract_skeleton
    from indexer.tokens import count_tokens

    config = Config(root=root)
    files = list(scan_directory(config.root, config.ignore_patterns))
    existing_hashes = db.get_all_file_hashes()
    changes = detect_changes(existing_hashes, files)

    total_changes = len(changes.added) + len(changes.modified) + len(changes.deleted)
    if total_changes == 0:
        save_freshness(db, root)
        click.echo("Index is up to date.", err=True)
        return

    click.echo(
        f"  {len(changes.added)} added, "
        f"{len(changes.modified)} modified, "
        f"{len(changes.deleted)} deleted.",
        err=True,
    )

    for p in changes.deleted:
        db.delete_file(p)
    db.connect().commit()

    to_index = changes.added + changes.modified
    if to_index:
        for fi in to_index:
            lang = detect_language(fi.path)
            file_rec = FileRecord(
                id=None, path=fi.path, content_hash=fi.content_hash,
                last_modified=fi.last_modified, language=lang,
                line_count=fi.line_count, byte_size=fi.byte_size,
            )
            file_id = db.upsert_file(file_rec)
            db.delete_symbols_for_file(file_id)
            db.delete_refs_for_file(file_id)

            if lang is None:
                continue

            abs_path = config.root / fi.path
            result = parse_file(abs_path)
            if result is None:
                continue

            symbols = extract_symbols(result)
            if symbols:
                sym_records = [
                    SymbolRecord(
                        id=None, name=sym.name, kind=sym.kind, file_id=file_id,
                        line_start=sym.line_start, line_end=sym.line_end,
                        col_start=sym.col_start, col_end=sym.col_end,
                        signature=sym.signature, parent_symbol_id=None,
                    )
                    for sym in symbols
                ]
                db.insert_symbols(sym_records)

                parent_map = {
                    sym.name: sym.parent_name
                    for sym in symbols
                    if sym.parent_name
                }
                db.resolve_parent_symbols(file_id, parent_map)

            skeleton_text = extract_skeleton(result)
            if skeleton_text.strip():
                tok_count = count_tokens(skeleton_text)
                db.upsert_skeleton(file_id, skeleton_text, tok_count)

        db.connect().commit()

        symbols_by_lang: dict[str, set[str]] = {}
        parseable = [f for f in to_index if detect_language(f.path) is not None]
        for fi in parseable:
            lang = detect_language(fi.path)
            if lang is None:
                continue
            if lang not in symbols_by_lang:
                symbols_by_lang[lang] = db.get_all_symbol_names(language=lang)
            known_symbols = symbols_by_lang[lang]
            if not known_symbols:
                continue

            abs_path = config.root / fi.path
            result = parse_file(abs_path)
            if result is None:
                continue

            frec = db.get_file(fi.path)
            if frec is None or frec.id is None:
                continue

            refs = extract_references(result, known_symbols)
            if refs:
                ref_records = [
                    RefRecord(
                        id=None, from_file_id=frec.id,
                        to_symbol_name=r.name, line=r.line,
                        resolved_symbol_id=None,
                    )
                    for r in refs
                ]
                db.insert_refs(ref_records)

        db.connect().commit()

    save_freshness(db, root)
    click.echo("Index updated.", err=True)
