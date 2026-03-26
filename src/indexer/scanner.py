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


def _should_descend(rel_dir: str, allow_patterns: list[str]) -> bool:
    """Check if rel_dir could be an ancestor of any allowed path.

    For pattern ``vendor/my-lib/**`` and rel_dir ``vendor``, returns True
    because we need to descend into ``vendor/`` to reach the allowed subtree.
    For rel_dir ``vendor/other``, returns False — prune immediately.
    """
    parts = rel_dir.replace("\\", "/").split("/")
    for pattern in allow_patterns:
        p = pattern.lstrip("/").replace("\\", "/")
        # ** at start can match any depth — always descend
        if p.startswith("**/"):
            return True
        pat_parts = p.rstrip("/").split("/")
        match = True
        for i, part in enumerate(parts):
            if i >= len(pat_parts):
                # rel_dir is deeper than the pattern — could still match
                # if the pattern ends with ** or a glob
                match = False
                break
            # If the pattern segment contains a glob, assume it could match
            if any(c in pat_parts[i] for c in ("*", "?", "[")):
                break
            if pat_parts[i] != part:
                match = False
                break
        if match:
            return True
    return False


def scan_directory(
    root: Path,
    ignore_patterns: list[str],
    allow_patterns: list[str] | None = None,
) -> Iterator[FileInfo]:
    all_patterns = ignore_patterns + _load_gitignore(root)
    ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)
    allow_spec = (
        pathspec.PathSpec.from_lines("gitwildmatch", allow_patterns)
        if allow_patterns
        else None
    )

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        # Prune ignored directories, but keep those needed for allow-list descent
        kept = []
        for d in dirnames:
            dir_match_path = os.path.join(rel_dir, d) + "/" if rel_dir else d + "/"
            is_ignored = d.startswith(".") or ignore_spec.match_file(dir_match_path)

            if is_ignored:
                if allow_spec and _should_descend(
                    os.path.join(rel_dir, d) if rel_dir else d,
                    allow_patterns,  # type: ignore[arg-type]
                ):
                    kept.append(d)
                # else: pruned
            else:
                kept.append(d)
        dirnames[:] = kept

        for fname in filenames:
            if fname.startswith("."):
                continue
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname

            if ignore_spec.match_file(rel_path):
                # Ignored — but check if allow overrides
                if not (allow_spec and allow_spec.match_file(rel_path)):
                    continue

            abs_path = Path(dirpath) / fname
            try:
                stat = abs_path.stat()
                content_hash = _hash_file(abs_path)
                # Count lines (binary files will raise)
                text = abs_path.read_text(errors="ignore")
                line_count = text.count("\n") + (
                    1 if text and not text.endswith("\n") else 0
                )
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


def detect_changes(
    existing_hashes: dict[str, str], scanned: list[FileInfo]
) -> ChangeSet:
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
    return ChangeSet(
        added=added, modified=modified, deleted=deleted, unchanged=unchanged
    )
