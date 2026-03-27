"""Configuration for the indexer."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

INDEXER_DIR = ".indexer"
DB_NAME = "index.db"
CONFIG_NAME = "config.json"
ERROR_LOG_NAME = "errors.log"

# These patterns seed a new config file. Once the config file exists,
# it is the sole source of truth — this list is never used at runtime.
_SEED_IGNORE = [
    ".git",
    ".indexer",
    "__pycache__",
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.o",
    "*.a",
    "*.class",
    "*.jar",
    "*.wasm",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.pdf",
    "*.zip",
    "*.tar.gz",
    "*.tgz",
]

# Always excluded regardless of config — safety invariant.
_ALWAYS_IGNORE = [".git", ".indexer"]


@dataclass
class Config:
    root: Path
    token_budget: int = 4096
    ignore: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)

    @property
    def indexer_dir(self) -> Path:
        return self.root / INDEXER_DIR

    @property
    def db_path(self) -> Path:
        return self.indexer_dir / DB_NAME

    @property
    def config_path(self) -> Path:
        return self.indexer_dir / CONFIG_NAME

    @property
    def ignore_patterns(self) -> list[str]:
        # Ensure safety patterns are always present
        patterns = list(self.ignore)
        for p in _ALWAYS_IGNORE:
            if p not in patterns:
                patterns.append(p)
        return patterns

    @property
    def allow_patterns(self) -> list[str]:
        return list(self.allow)


def find_project_root(start: Path) -> Path:
    """Walk up from *start* looking for ``.git/``. Falls back to *start* if not found."""
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return start.resolve()
        current = parent


def load_or_create_config(root: Path) -> Config:
    """Load config from .indexer/config.json, or create it with seed defaults."""
    indexer_dir = root / INDEXER_DIR
    config_path = indexer_dir / CONFIG_NAME

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return Config(
                root=root,
                ignore=data.get("ignore", list(_SEED_IGNORE)),
                allow=data.get("allow", []),
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(
                f"Warning: failed to parse {config_path}: {e}. Using defaults.",
                file=sys.stderr,
            )

    # Create config with seed defaults
    config = Config(root=root, ignore=list(_SEED_IGNORE), allow=[])
    save_config(config)
    return config


def save_config(config: Config) -> None:
    """Write current config state to .indexer/config.json."""
    config.indexer_dir.mkdir(parents=True, exist_ok=True)
    data = {"ignore": config.ignore, "allow": config.allow}
    config.config_path.write_text(json.dumps(data, indent=2) + "\n")
