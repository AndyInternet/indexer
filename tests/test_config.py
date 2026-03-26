"""Tests for config loading, saving, and the allow/ignore mechanism."""

from __future__ import annotations

import json
from pathlib import Path

from indexer.config import (
    _SEED_IGNORE,
    Config,
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
