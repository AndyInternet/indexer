"""Tests for config loading, saving, and the allow/ignore mechanism."""

from __future__ import annotations

import json
from pathlib import Path

from indexer.config import (
    _SEED_IGNORE,
    Config,
    find_project_root,
    load_or_create_config,
    save_config,
)


def test_load_creates_config_file(tmp_path: Path):
    """First call creates .indexer/config.json with seed defaults."""
    config = load_or_create_config(tmp_path)
    assert config.config_path.exists()
    data = json.loads(config.config_path.read_text())
    assert data["ignore"] == _SEED_IGNORE
    assert data["allow"] == []


def test_load_reads_existing_config(tmp_path: Path):
    """If config.json already exists, load it instead of seeding."""
    indexer_dir = tmp_path / ".indexer"
    indexer_dir.mkdir()
    cfg = {"ignore": ["foo"], "allow": ["bar/**"]}
    (indexer_dir / "config.json").write_text(json.dumps(cfg))

    config = load_or_create_config(tmp_path)
    assert config.ignore == ["foo"]
    assert config.allow == ["bar/**"]


def test_load_handles_corrupt_json(tmp_path: Path):
    """Corrupt JSON falls back to seed defaults."""
    indexer_dir = tmp_path / ".indexer"
    indexer_dir.mkdir()
    (indexer_dir / "config.json").write_text("{bad json")

    config = load_or_create_config(tmp_path)
    assert config.ignore == _SEED_IGNORE
    assert config.allow == []


def test_save_config_roundtrips(tmp_path: Path):
    """save_config writes JSON that load_or_create_config can read back."""
    config = Config(root=tmp_path, ignore=["a", "b"], allow=["c/**"])
    save_config(config)
    assert config.config_path.exists()

    loaded = load_or_create_config(tmp_path)
    assert loaded.ignore == ["a", "b"]
    assert loaded.allow == ["c/**"]


def test_ignore_patterns_always_include_safety():
    """ignore_patterns always includes .git and .indexer even if user removes them."""
    config = Config(root=Path("/tmp"), ignore=["foo"])
    patterns = config.ignore_patterns
    assert ".git" in patterns
    assert ".indexer" in patterns
    assert "foo" in patterns


def test_allow_patterns_returns_copy():
    """allow_patterns returns a copy, not the original list."""
    config = Config(root=Path("/tmp"), allow=["x/**"])
    patterns = config.allow_patterns
    patterns.append("y/**")
    assert "y/**" not in config.allow


def test_find_project_root_with_git(tmp_path: Path):
    """Finds .git directory when walking up from a subdirectory."""
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "pkg"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == tmp_path


def test_find_project_root_no_markers(tmp_path: Path):
    """Falls back to start directory when no .git found."""
    subdir = tmp_path / "some" / "deep" / "path"
    subdir.mkdir(parents=True)
    assert find_project_root(subdir) == subdir


def test_find_project_root_at_root(tmp_path: Path):
    """Returns start when .git is at start itself."""
    (tmp_path / ".git").mkdir()
    assert find_project_root(tmp_path) == tmp_path
