"""Token-budgeted, scope-aware repo map rendering."""

from __future__ import annotations

from indexer.db import Database, SymbolRecord
from indexer.tokens import count_tokens


def render_repo_map(
    db: Database,
    pagerank_scores: dict[str, float],
    token_budget: int = 4096,
) -> str:
    """Render a repo map fitting within the token budget.

    Uses binary search to find the score threshold that maximizes
    content while staying within budget. Output uses scope-aware
    elided format for optimal LLM consumption.
    """
    if not pagerank_scores:
        return "# Empty index — no files found."

    # Collect all files with their symbols, sorted by PageRank
    ranked_files = list(pagerank_scores.keys())
    file_symbols: dict[str, list[SymbolRecord]] = {}

    for path in ranked_files:
        frec = db.get_file(path)
        if frec and frec.id is not None:
            syms = db.get_symbols_by_file(frec.id)
            if syms:
                file_symbols[path] = syms

    # Binary search: find how many files we can include
    lo, hi = 1, len(ranked_files)
    best_output = ""

    while lo <= hi:
        mid = (lo + hi) // 2
        output = _render_files(ranked_files[:mid], file_symbols)
        tokens = count_tokens(output)

        if tokens <= token_budget:
            best_output = output
            lo = mid + 1
        else:
            hi = mid - 1

    if not best_output:
        # At minimum, show the top file
        best_output = _render_files(ranked_files[:1], file_symbols)

    return best_output


def _render_files(paths: list[str], file_symbols: dict[str, list[SymbolRecord]]) -> str:
    """Render selected files in scope-aware elided format."""
    sections = []

    for path in paths:
        syms = file_symbols.get(path, [])
        if not syms:
            sections.append(f"{path}")
            continue

        lines = [f"{path}:"]

        # Group symbols by parent (class containment)
        top_level = []
        by_parent: dict[str, list[SymbolRecord]] = {}

        for s in syms:
            if s.parent_symbol_id is not None:
                # Find parent name
                parent = next((p for p in syms if p.id == s.parent_symbol_id), None)
                if parent:
                    by_parent.setdefault(parent.name, []).append(s)
                    continue
            top_level.append(s)

        for sym in top_level:
            if sym.kind in ("class", "interface"):
                lines.append(f"⋮")
                sig = sym.signature or sym.name
                lines.append(f"  {sig}:")
                children = by_parent.get(sym.name, [])
                for child in children:
                    lines.append(f"  ⋮")
                    child_sig = child.signature or child.name
                    lines.append(f"    {child_sig}")
            else:
                lines.append(f"⋮")
                sig = sym.signature or sym.name
                lines.append(f"  {sig}")

        sections.append("\n".join(lines))

    return "\n\n".join(sections)
