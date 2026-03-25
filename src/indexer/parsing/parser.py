"""Tree-sitter parsing wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tree_sitter

from .languages import detect_language, get_parser


@dataclass
class ParseResult:
    tree: tree_sitter.Tree
    source: bytes
    language: str
    file_path: str


def parse_file(file_path: str | Path) -> ParseResult | None:
    path = Path(file_path)
    lang = detect_language(path)
    if lang is None:
        return None

    parser = get_parser(lang)
    if parser is None:
        return None

    try:
        source = path.read_bytes()
    except OSError:
        return None

    tree = parser.parse(source)
    return ParseResult(tree=tree, source=source, language=lang, file_path=str(path))
