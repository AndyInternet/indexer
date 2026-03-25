"""Language detection and tree-sitter parser loading."""

from __future__ import annotations

from pathlib import Path

import tree_sitter

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".cs": "c_sharp",
}

# tree-sitter pip package names for each language
_GRAMMAR_PACKAGES: dict[str, str] = {
    "python": "tree_sitter_python",
    "typescript": "tree_sitter_typescript",
    "tsx": "tree_sitter_typescript",
    "javascript": "tree_sitter_javascript",
    "go": "tree_sitter_go",
    "rust": "tree_sitter_rust",
    "java": "tree_sitter_java",
    "c": "tree_sitter_c",
    "cpp": "tree_sitter_cpp",
    "ruby": "tree_sitter_ruby",
    "c_sharp": "tree_sitter_c_sharp",
}

_parser_cache: dict[str, tree_sitter.Parser] = {}
_language_cache: dict[str, tree_sitter.Language] = {}


def detect_language(file_path: str | Path) -> str | None:
    ext = Path(file_path).suffix.lower()
    return LANGUAGE_MAP.get(ext)


def _load_language(lang: str) -> tree_sitter.Language | None:
    if lang in _language_cache:
        return _language_cache[lang]

    pkg_name = _GRAMMAR_PACKAGES.get(lang)
    if pkg_name is None:
        return None

    try:
        mod = __import__(pkg_name)
        # tsx is a submodule of tree_sitter_typescript
        if lang == "tsx":
            language_fn = mod.language_tsx
        elif lang == "typescript":
            language_fn = mod.language_typescript
        else:
            language_fn = mod.language
        ts_lang = tree_sitter.Language(language_fn())
        _language_cache[lang] = ts_lang
        return ts_lang
    except (ImportError, AttributeError):
        return None


def get_parser(lang: str) -> tree_sitter.Parser | None:
    if lang in _parser_cache:
        return _parser_cache[lang]

    ts_lang = _load_language(lang)
    if ts_lang is None:
        return None

    parser = tree_sitter.Parser(ts_lang)
    _parser_cache[lang] = parser
    return parser
