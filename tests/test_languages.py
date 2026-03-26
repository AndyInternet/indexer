"""Tests for language detection and parser loading."""

from __future__ import annotations

from pathlib import Path

from indexer.parsing.languages import detect_language, get_parser


def test_detect_language_python():
    assert detect_language(Path("main.py")) == "python"


def test_detect_language_typescript():
    assert detect_language(Path("app.ts")) == "typescript"
    assert detect_language(Path("app.tsx")) == "tsx"


def test_detect_language_go():
    assert detect_language(Path("main.go")) == "go"


def test_detect_language_unknown():
    assert detect_language(Path("data.xyz")) is None
    assert detect_language(Path("README.md")) is None


def test_get_parser_python():
    """get_parser returns a Parser instance for supported languages."""
    parser = get_parser("python")
    assert parser is not None


def test_get_parser_cached():
    """Second call returns the same cached object."""
    p1 = get_parser("python")
    p2 = get_parser("python")
    assert p1 is p2


def test_get_parser_unknown():
    """Unknown language returns None."""
    assert get_parser("brainfuck") is None
