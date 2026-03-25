"""Code skeleton generation — strips implementation bodies, keeps signatures."""

from __future__ import annotations

from indexer.parsing.parser import ParseResult

# Node types that represent function/method bodies
BODY_NODE_TYPES = {
    "python": {"block"},
    "typescript": {"statement_block"},
    "tsx": {"statement_block"},
    "javascript": {"statement_block"},
    "go": {"block"},
    "rust": {"block"},
    "java": {"block"},
    "c": {"compound_statement"},
    "cpp": {"compound_statement"},
    "ruby": {"body_statement"},
    "c_sharp": {"block"},
}

# Node types that are definitions whose bodies should be elided
FUNCTION_LIKE_NODES: dict[str, set[str]] = {
    "python": {"function_definition"},
    "typescript": {"function_declaration", "method_definition", "arrow_function"},
    "tsx": {"function_declaration", "method_definition", "arrow_function"},
    "javascript": {"function_declaration", "method_definition", "arrow_function"},
    "go": {"function_declaration", "method_declaration"},
    "rust": {"function_item"},
    "java": {"method_declaration", "constructor_declaration"},
    "c": {"function_definition"},
    "cpp": {"function_definition"},
    "ruby": {"method"},
    "c_sharp": {"method_declaration", "constructor_declaration"},
}

# Node types to always include verbatim
INCLUDE_VERBATIM: dict[str, set[str]] = {
    "python": {"import_statement", "import_from_statement", "decorated_definition"},
    "typescript": {"import_statement", "export_statement", "type_alias_declaration", "interface_declaration"},
    "tsx": {"import_statement", "export_statement", "type_alias_declaration", "interface_declaration"},
    "javascript": {"import_statement", "export_statement"},
    "go": {"import_declaration", "package_clause", "type_declaration"},
    "rust": {"use_declaration", "mod_item", "type_item", "const_item", "static_item"},
    "java": {"import_declaration", "package_declaration"},
    "c": {"preproc_include", "preproc_def", "type_definition"},
    "cpp": {"preproc_include", "preproc_def", "using_declaration", "type_definition", "namespace_definition"},
    "ruby": {"call"},
    "c_sharp": {"using_directive", "namespace_declaration"},
}

# Class-like node types (recurse into them)
CLASS_LIKE_NODES: dict[str, set[str]] = {
    "python": {"class_definition"},
    "typescript": {"class_declaration"},
    "tsx": {"class_declaration"},
    "javascript": {"class_declaration"},
    "go": set(),
    "rust": {"impl_item", "trait_item"},
    "java": {"class_declaration", "interface_declaration"},
    "c": set(),
    "cpp": {"class_specifier", "struct_specifier"},
    "ruby": {"class", "module"},
    "c_sharp": {"class_declaration", "interface_declaration"},
}


def extract_skeleton(result: ParseResult) -> str:
    """Generate a code skeleton from a parsed file."""
    lang = result.language
    source = result.source
    lines: list[str] = []

    _walk_skeleton(
        result.tree.root_node, source, lang, lines, depth=0
    )

    return "\n".join(lines)


def _get_signature_text(node, source: bytes, lang: str) -> str:
    """Get everything before the body of a function-like node."""
    body_types = BODY_NODE_TYPES.get(lang, set())
    for child in node.children:
        if child.type in body_types:
            sig = source[node.start_byte:child.start_byte].decode("utf-8", errors="replace").rstrip()
            return sig

    # No body — return first line
    full = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    return full.split("\n")[0]


def _get_class_header(node, source: bytes, lang: str) -> str:
    """Get the class/struct header line(s)."""
    body_types = BODY_NODE_TYPES.get(lang, set()) | {"class_body", "body", "body_statement"}
    for child in node.children:
        if child.type in body_types:
            header = source[node.start_byte:child.start_byte].decode("utf-8", errors="replace").rstrip()
            return header

    full = source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
    return full.split("\n")[0]


def _node_text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _walk_skeleton(
    node, source: bytes, lang: str,
    lines: list[str], depth: int,
) -> None:
    """Walk AST and build skeleton output."""
    func_nodes = FUNCTION_LIKE_NODES.get(lang, set())
    include_nodes = INCLUDE_VERBATIM.get(lang, set())
    class_nodes = CLASS_LIKE_NODES.get(lang, set())

    for child in node.children:
        # Decorators — include, then the definition will follow
        if child.type == "decorator":
            lines.append(_node_text(child, source))
            continue

        # Imports and other verbatim includes
        if child.type in include_nodes:
            text = _node_text(child, source)
            # For decorated_definition in Python, handle specially
            if child.type == "decorated_definition":
                _walk_skeleton(child, source, lang, lines, depth)
                continue
            lines.append(text)
            continue

        # Class-like nodes — include header, recurse into body
        if child.type in class_nodes:
            header = _get_class_header(child, source, lang)
            lines.append(header)

            # Find the body and recurse
            body_types = BODY_NODE_TYPES.get(lang, set()) | {"class_body", "body", "body_statement"}
            body_found = False
            for sub in child.children:
                if sub.type in body_types:
                    _walk_skeleton(sub, source, lang, lines, depth + 1)
                    body_found = True
                    break
            if not body_found:
                _walk_skeleton(child, source, lang, lines, depth + 1)

            lines.append("")
            continue

        # Function-like nodes — include signature + ...
        if child.type in func_nodes:
            sig = _get_signature_text(child, source, lang)
            if lang == "python":
                lines.append(f"{sig}")
                indent = "    " * (depth + 1)
                lines.append(f"{indent}...")
            else:
                lines.append(f"{sig} {{ ... }}")
            continue

        # Module-level variable assignments with type annotations (Python)
        if lang == "python" and child.type in ("expression_statement",):
            text = _node_text(child, source)
            # Include if it looks like a constant or has type annotation
            if ":" in text or text.split("=")[0].strip().isupper():
                lines.append(text)
            continue

        # Module-level const/let/var declarations (JS/TS)
        if lang in ("typescript", "tsx", "javascript") and child.type == "lexical_declaration":
            text = _node_text(child, source)
            # Include type declarations and exported consts
            if "type " in text or "interface " in text or len(text.split("\n")) <= 2:
                lines.append(text)
            continue

        # Recurse for top-level program/module structures
        if child.type in ("program", "module", "translation_unit", "source_file",
                          "compilation_unit", "declaration_list"):
            _walk_skeleton(child, source, lang, lines, depth)
