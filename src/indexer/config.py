"""Configuration for the indexer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

INDEXER_DIR = ".indexer"
DB_NAME = "index.db"

DEFAULT_IGNORE = [
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


@dataclass
class Config:
    root: Path
    token_budget: int = 4096
    extra_ignore: list[str] = field(default_factory=list)

    @property
    def indexer_dir(self) -> Path:
        return self.root / INDEXER_DIR

    @property
    def db_path(self) -> Path:
        return self.indexer_dir / DB_NAME

    @property
    def ignore_patterns(self) -> list[str]:
        return DEFAULT_IGNORE + self.extra_ignore
