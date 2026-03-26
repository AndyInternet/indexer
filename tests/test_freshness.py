"""Tests for freshness detection via fingerprinting."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from indexer.db import Database
from indexer.freshness import (
    _config_fingerprint,
    _git_fingerprint,
    check_freshness,
    compute_fingerprint,
    save_freshness,
)


def _mock_subprocess_run(
    monkeypatch, head_stdout="abc123\n", status_stdout="", fail=False
):
    """Mock subprocess.run for git commands."""

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if fail:
            result.returncode = 128
            result.stdout = ""
            return result
        if "rev-parse" in cmd:
            result.returncode = 0
            result.stdout = head_stdout
        elif "status" in cmd:
            result.returncode = 0
            result.stdout = status_stdout
        else:
            result.returncode = 1
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)


def test_git_fingerprint_returns_hash(monkeypatch, tmp_path: Path):
    """Successful git calls return a sha256 hex digest."""
    _mock_subprocess_run(monkeypatch)
    fp = _git_fingerprint(tmp_path)
    assert fp is not None
    assert len(fp) == 64


def test_git_fingerprint_not_git_repo(monkeypatch, tmp_path: Path):
    """Non-git directory returns None."""
    _mock_subprocess_run(monkeypatch, fail=True)
    assert _git_fingerprint(tmp_path) is None


def test_config_fingerprint_with_config(tmp_path: Path):
    """Existing config.json is hashed."""
    indexer_dir = tmp_path / ".indexer"
    indexer_dir.mkdir()
    (indexer_dir / "config.json").write_text(json.dumps({"ignore": [".git"]}))
    fp = _config_fingerprint(tmp_path)
    assert len(fp) == 64


def test_config_fingerprint_no_config(tmp_path: Path):
    """Missing config returns empty string."""
    assert _config_fingerprint(tmp_path) == ""


def test_compute_fingerprint_git(monkeypatch, tmp_path: Path):
    """Uses git fingerprint when available."""
    _mock_subprocess_run(monkeypatch)
    fp = compute_fingerprint(tmp_path)
    assert len(fp) == 64


def test_compute_fingerprint_changes_with_status(monkeypatch, tmp_path: Path):
    """Different git status produces different fingerprint."""
    _mock_subprocess_run(monkeypatch, status_stdout="")
    fp1 = compute_fingerprint(tmp_path)
    _mock_subprocess_run(monkeypatch, status_stdout=" M file.py\n")
    fp2 = compute_fingerprint(tmp_path)
    assert fp1 != fp2


def test_check_freshness_fresh(db: Database, monkeypatch, tmp_path: Path):
    """Stored fingerprint matching current returns None (fresh)."""
    _mock_subprocess_run(monkeypatch)
    save_freshness(db, tmp_path)
    reason = check_freshness(db, tmp_path)
    assert reason is None


def test_check_freshness_stale(db: Database, monkeypatch, tmp_path: Path):
    """Mismatched fingerprint returns a reason string."""
    _mock_subprocess_run(monkeypatch, head_stdout="old_commit\n")
    save_freshness(db, tmp_path)
    _mock_subprocess_run(monkeypatch, head_stdout="new_commit\n")
    reason = check_freshness(db, tmp_path)
    assert reason == "files changed"
