"""File discovery, hashing, and change detection."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pathspec


@dataclass
class FileInfo:
    path: str  # relative to root
    abs_path: Path
    content_hash: str
    last_modified: float
    byte_size: int
    line_count: int


@dataclass
class ChangeSet:
    added: list[FileInfo]
    modified: list[FileInfo]
    deleted: list[str]  # relative paths
    unchanged: list[str]


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _load_gitignore(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if gitignore.exists():
        return gitignore.read_text().splitlines()
    return []


def scan_directory(root: Path, ignore_patterns: list[str]) -> Iterator[FileInfo]:
    all_patterns = ignore_patterns + _load_gitignore(root)
    spec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        # Prune ignored directories
        dirnames[:] = [
            d for d in dirnames
            if not spec.match_file(os.path.join(rel_dir, d) + "/" if rel_dir else d + "/")
            and not d.startswith(".")
        ]

        for fname in filenames:
            if fname.startswith("."):
                continue
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            if spec.match_file(rel_path):
                continue

            abs_path = Path(dirpath) / fname
            try:
                stat = abs_path.stat()
                content_hash = _hash_file(abs_path)
                # Count lines (binary files will raise)
                text = abs_path.read_text(errors="ignore")
                line_count = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            except (OSError, UnicodeDecodeError):
                continue

            yield FileInfo(
                path=rel_path,
                abs_path=abs_path,
                content_hash=content_hash,
                last_modified=stat.st_mtime,
                byte_size=stat.st_size,
                line_count=line_count,
            )


def detect_changes(existing_hashes: dict[str, str], scanned: list[FileInfo]) -> ChangeSet:
    added = []
    modified = []
    unchanged = []
    seen_paths = set()

    for fi in scanned:
        seen_paths.add(fi.path)
        old_hash = existing_hashes.get(fi.path)
        if old_hash is None:
            added.append(fi)
        elif old_hash != fi.content_hash:
            modified.append(fi)
        else:
            unchanged.append(fi.path)

    deleted = [p for p in existing_hashes if p not in seen_paths]
    return ChangeSet(added=added, modified=modified, deleted=deleted, unchanged=unchanged)
