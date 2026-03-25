"""Dependency graph construction from the index database."""

from __future__ import annotations

import networkx as nx

from indexer.db import Database


def build_dependency_graph(db: Database) -> nx.DiGraph:
    """Build a directed graph where nodes are file paths and edges are cross-file references."""
    G = nx.DiGraph()

    # Add all files as nodes
    files = db.get_all_files()
    file_id_to_path = {}
    for f in files:
        G.add_node(f.path)
        file_id_to_path[f.id] = f.path

    # Build symbol name -> defining file(s) lookup
    conn = db.connect()
    rows = conn.execute(
        "SELECT DISTINCT name, file_id FROM symbols"
    ).fetchall()
    symbol_to_files: dict[str, list[int]] = {}
    for r in rows:
        symbol_to_files.setdefault(r["name"], []).append(r["file_id"])

    # Process all references to build edges
    refs = conn.execute("SELECT from_file_id, to_symbol_name FROM refs").fetchall()

    edge_weights: dict[tuple[str, str], int] = {}
    for ref in refs:
        from_file_id = ref["from_file_id"]
        to_symbol_name = ref["to_symbol_name"]

        target_file_ids = symbol_to_files.get(to_symbol_name, [])
        from_path = file_id_to_path.get(from_file_id)
        if not from_path:
            continue

        for target_fid in target_file_ids:
            to_path = file_id_to_path.get(target_fid)
            if to_path and to_path != from_path:
                edge = (from_path, to_path)
                edge_weights[edge] = edge_weights.get(edge, 0) + 1

    for (src, dst), weight in edge_weights.items():
        G.add_edge(src, dst, weight=weight)

    return G
