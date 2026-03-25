"""Symbol and reference extraction from tree-sitter ASTs."""

from __future__ import annotations

from dataclasses import dataclass

from .parser import ParseResult

# AST node types that represent definitions, per language
DEFINITION_NODES: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "arrow_function": "function",
    },
    "tsx": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
        "arrow_function": "function",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_declaration": "type",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "class",
        "enum_item": "type",
        "impl_item": "class",
        "trait_item": "interface",
    },
    "java": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "class",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "class",
    },
    "ruby": {
        "method": "function",
        "class": "class",
        "module": "class",
    },
    "c_sharp": {
        "method_declaration": "method",
        "class_declaration": "class",
        "interface_declaration": "interface",
    },
}

# Node types containing import statements
IMPORT_NODES: dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement"},
    "typescript": {"import_statement", "import_clause"},
    "tsx": {"import_statement", "import_clause"},
    "javascript": {"import_statement"},
    "go": {"import_declaration"},
    "rust": {"use_declaration"},
    "java": {"import_declaration"},
    "c": {"preproc_include"},
    "cpp": {"preproc_include", "using_declaration"},
    "ruby": {"call"},  # require/require_relative
    "c_sharp": {"using_directive"},
}


@dataclass
class Symbol:
    name: str
    kind: str
    line_start: int
    line_end: int
    col_start: int
    col_end: int
    signature: str
    parent_name: str | None = None


@dataclass
class Reference:
    name: str
    line: int


def _get_node_name(node, source: bytes, language: str) -> str | None:
    """Extract the name from a definition node."""
    # Most languages use a 'name' field
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    # Go method declarations: func (r *Receiver) MethodName(...)
    if language == "go" and node.type == "method_declaration":
        name_node = node.child_by_field_name("name")
        if name_node:
            return source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    # For arrow functions assigned to variables: const foo = () => {}
    if node.type == "arrow_function" and node.parent:
        parent = node.parent
        if parent.type == "variable_declarator":
            vname = parent.child_by_field_name("name")
            if vname:
                return source[vname.start_byte:vname.end_byte].decode("utf-8", errors="replace")

    return None


def _get_signature(node, source: bytes, language: str) -> str:
    """Extract the signature (everything before the body)."""
    body_types = {"block", "statement_block", "compound_statement", "class_body", "body"}

    for child in node.children:
        if child.type in body_types:
            sig = source[node.start_byte:child.start_byte].decode("utf-8", errors="replace").rstrip()
            # Clean up trailing colon/brace
            return sig.rstrip("{").rstrip(":").rstrip()

    # No body found — use the full node text (truncated)
    full = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    lines = full.split("\n")
    return lines[0] if lines else full[:200]


def extract_symbols(result: ParseResult) -> list[Symbol]:
    """Extract all symbol definitions from a parsed file."""
    lang = result.language
    defs = DEFINITION_NODES.get(lang, {})
    if not defs:
        return []

    symbols = []
    _walk_for_symbols(result.tree.root_node, result.source, lang, defs, symbols, parent_name=None)
    return symbols


def _walk_for_symbols(
    node, source: bytes, language: str,
    defs: dict[str, str], symbols: list[Symbol],
    parent_name: str | None,
) -> None:
    """Recursively walk the AST to find definition nodes."""
    if node.type in defs:
        kind = defs[node.type]
        name = _get_node_name(node, source, language)
        if name:
            sig = _get_signature(node, source, language)
            symbols.append(Symbol(
                name=name,
                kind=kind,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                col_start=node.start_point[1],
                col_end=node.end_point[1],
                signature=sig,
                parent_name=parent_name,
            ))
            # For class methods, recurse with parent
            current_parent = name if kind in ("class", "interface") else parent_name
            for child in node.children:
                _walk_for_symbols(child, source, language, defs, symbols, current_parent)
            return

    for child in node.children:
        _walk_for_symbols(child, source, language, defs, symbols, parent_name)


def extract_references(result: ParseResult, known_symbols: set[str] | None = None) -> list[Reference]:
    """Extract identifier references from a parsed file.

    If known_symbols is provided, only references to those names are returned.
    """
    refs = []
    _walk_for_refs(result.tree.root_node, result.source, result.language, refs, known_symbols)
    return refs


def _walk_for_refs(
    node, source: bytes, language: str,
    refs: list[Reference], known_symbols: set[str] | None,
) -> None:
    """Walk AST to find identifier references."""
    if node.type == "identifier" or node.type == "type_identifier":
        name = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        if known_symbols is None or name in known_symbols:
            refs.append(Reference(name=name, line=node.start_point[0] + 1))
    for child in node.children:
        _walk_for_refs(child, source, language, refs, known_symbols)
